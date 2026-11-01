from flask import Flask, render_template, request, send_file, redirect, url_for, session, flash
import pandas as pd
import os
import plotly
import plotly.express as px
import json
import logging
from logging.handlers import RotatingFileHandler
import uuid

from flask_wtf.csrf import CSRFProtect

from config.settings import Config
from src.cleaning import clean_sales_data
from src.analysis import analyze_sales_data
from src.utils import (
    allowed_file,
    sanitize_filename,
    validate_dataframe_size,
    validate_required_columns,
    get_file_size_mb
)
from src.duckdb_manager import db_manager
from src.session_manager import session_manager

# -----------------------------------
# Flask App Configuration
# -----------------------------------

app = Flask(__name__)
app.config.from_object(Config)

# Validate configuration
Config.validate()

# Initialize CSRF Protection
csrf = CSRFProtect(app)

# -----------------------------------
# Logging Configuration
# -----------------------------------

if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')

    file_handler = RotatingFileHandler(
        'logs/sales_analytics.log',
        maxBytes=10240000,  # 10MB
        backupCount=10
    )

    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))

    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Sales Analytics startup')

# -----------------------------------
# Home page
# -----------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# -----------------------------------
# Upload and clean dataset
# -----------------------------------

@app.route("/upload", methods=["POST"])
def upload_file():
    """
    Handle file upload, validation, cleaning, and analysis.
    """
    try:
        file = request.files.get("file")

        # -----------------------------------
        # FILE VALIDATION
        # -----------------------------------

        # Check if file exists
        if file is None or file.filename == "":
            flash("No file selected. Please choose a CSV or Excel file to upload.", "error")
            return redirect(url_for("home"))

        # Check file extension
        if not allowed_file(file.filename):
            flash("Invalid file type. Only CSV and Excel (.xlsx) files are allowed.", "error")
            return redirect(url_for("home"))

        # Sanitize filename
        original_filename = file.filename
        safe_filename = sanitize_filename(original_filename)

        if not safe_filename:
            flash("Invalid filename. Please rename your file and try again.", "error")
            return redirect(url_for("home"))

        # -----------------------------------
        # SAVE FILE
        # -----------------------------------

        file_path = os.path.join(
            Config.UPLOAD_FOLDER,
            safe_filename
        )

        file.save(file_path)

        # Log file size
        file_size_mb = get_file_size_mb(file_path)
        app.logger.info(f"File uploaded: {safe_filename} ({file_size_mb:.2f} MB)")

        # -----------------------------------
        # READ DATASET
        # -----------------------------------

        try:
            if safe_filename.lower().endswith(".csv"):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)

        except Exception as e:
            app.logger.error(f"Error reading file {safe_filename}: {str(e)}")
            flash("Unable to read the uploaded file. Please ensure it's a valid CSV or Excel file.", "error")
            # Clean up uploaded file
            if os.path.exists(file_path):
                os.remove(file_path)
            return redirect(url_for("home"))

        # -----------------------------------
        # VALIDATE DATAFRAME
        # -----------------------------------

        # Check size constraints
        size_valid, size_error = validate_dataframe_size(df)
        if not size_valid:
            flash(size_error, "error")
            if os.path.exists(file_path):
                os.remove(file_path)
            return redirect(url_for("home"))

        # Check required columns
        columns_valid, columns_error = validate_required_columns(df)
        if not columns_valid:
            flash(columns_error, "error")
            if os.path.exists(file_path):
                os.remove(file_path)
            return redirect(url_for("home"))

        app.logger.info(f"Dataset validated: {len(df)} rows, {len(df.columns)} columns")

        # -----------------------------------
        # BEFORE CLEANING METRICS
        # -----------------------------------

        before_rows = len(df)
        before_columns = len(df.columns)
        before_duplicates = df.duplicated().sum()
        before_missing = int(df.isnull().sum().sum())

        # -----------------------------------
        # CLEAN DATA
        # -----------------------------------

        try:
            cleaned_df = clean_sales_data(df)
            app.logger.info(f"Data cleaning completed: {len(cleaned_df)} rows retained")

        except Exception as e:
            app.logger.error(f"Error during data cleaning: {str(e)}")
            flash("An error occurred while cleaning the data. Please check your file format.", "error")
            if os.path.exists(file_path):
                os.remove(file_path)
            return redirect(url_for("home"))

        # -----------------------------------
        # AFTER CLEANING METRICS
        # -----------------------------------

        after_rows = len(cleaned_df)
        after_columns = len(cleaned_df.columns)
        after_missing = int(cleaned_df.isnull().sum().sum())
        rows_removed = before_rows - after_rows

        # -----------------------------------
        # ANALYSIS
        # -----------------------------------

        try:
            analysis = analyze_sales_data(cleaned_df)
            app.logger.info("Sales analysis completed")

        except Exception as e:
            app.logger.error(f"Error during analysis: {str(e)}")
            flash("An error occurred while analyzing the data.", "error")
            if os.path.exists(file_path):
                os.remove(file_path)
            return redirect(url_for("home"))

        # -----------------------------------
        # SAVE CLEANED DATASET TO SESSION-DUCKDB DATABASE
        # -----------------------------------

        # Each upload gets its own isolated database (multi-user safe)
        dataset_session_id = str(uuid.uuid4())
        db_path = db_manager.create_database(dataset_session_id)

        try:
            db_manager.load_dataframe(
                db_path,
                cleaned_df,
                table_name=Config.DUCKDB_TABLE_NAME
            )
            app.logger.info(
                f"DuckDB dataset created: {db_path} "
                f"(session {dataset_session_id}, {len(cleaned_df)} rows)"
            )
        except Exception as e:
            app.logger.error(f"Error creating DuckDB dataset: {str(e)}")
            db_manager.delete_database(db_path)
            flash("Error initializing your dataset. Please try uploading again.", "error")
            return redirect(url_for("home"))

        # Register the session with the session manager.
        # Must use dataset_session_id (the same value stored in the cookie
        # and used to name the DuckDB file), not a fresh UUID.
        session_manager.register_session(dataset_session_id, db_path)

        # -----------------------------------
        # STORE CLEANING REPORT IN SESSION
        # -----------------------------------

        cleaning_report = {
            "before_rows": before_rows,
            "after_rows": after_rows,
            "before_columns": before_columns,
            "after_columns": after_columns,
            "duplicates": int(before_duplicates),
            "before_missing": before_missing,
            "after_missing": after_missing,
            "rows_removed": rows_removed,
            "filename": original_filename
        }

        session["cleaning_report"] = cleaning_report
        # Store the dataset session id so /dashboard and /api/chat can
        # access the correct isolated database.
        session["dataset_session_id"] = dataset_session_id
        session.permanent = True

        # -----------------------------------
        # REDIRECT TO RESULTS PAGE
        # -----------------------------------

        return redirect(url_for("result"))

    except Exception as e:
        app.logger.error(f"Unexpected error in upload_file: {str(e)}")
        flash("An unexpected error occurred. Please try again.", "error")
        return redirect(url_for("home"))


# -----------------------------------
# Cleaning Results Page
# -----------------------------------

@app.route("/result")
def result():
    """
    Display data cleaning report.
    """
    report = session.get("cleaning_report")

    if not report:
        flash("No cleaning report available. Please upload a dataset first.", "warning")
        return redirect(url_for("home"))

    return render_template("result.html", report=report)


# -----------------------------------
# Dashboard Page
# -----------------------------------

def _get_active_dataset():
    """
    Load the active user's dataset from their session-isolated DuckDB database.

    Returns:
        pd.DataFrame or None if no valid dataset exists for this session.
    """
    dataset_session_id = session.get("dataset_session_id")
    if not dataset_session_id:
        return None

    db_path = session_manager.get_database_path(dataset_session_id)
    if not db_path or not db_manager.database_exists(db_path):
        return None

    return db_manager.query(
        db_path,
        f"SELECT * FROM {Config.DUCKDB_TABLE_NAME}",
    )


@app.route("/dashboard")
def dashboard():
    """
    Display interactive analytics dashboard with filters.
    """
    # -----------------------------------
    # Load the session's dataset from DuckDB
    # -----------------------------------

    try:
        df = _get_active_dataset()

    except Exception as e:
        app.logger.error(f"Error loading session dataset: {str(e)}")
        df = None

    if df is None or df.empty:
        flash("Please upload a dataset first.", "warning")
        return redirect(url_for("home"))

    # Convert date
    if 'order_date' in df.columns:
        df["order_date"] = pd.to_datetime(
            df["order_date"],
            errors="coerce"
        )

    # -----------------------------------
    # Filter options (from full dataset)
    # -----------------------------------

    all_df = df.copy()

    cities = sorted(
        all_df["city"]
        .dropna()
        .unique()
        .tolist()
    ) if 'city' in all_df.columns else []

    categories = sorted(
        all_df["category"]
        .dropna()
        .unique()
        .tolist()
    ) if 'category' in all_df.columns else []

    products = sorted(
        all_df["product"]
        .dropna()
        .unique()
        .tolist()
    ) if 'product' in all_df.columns else []

    # -----------------------------------
    # Get selected filters
    # -----------------------------------

    selected_city = request.args.get("city", "")
    selected_category = request.args.get("category", "")
    selected_product = request.args.get("product", "")

    # -----------------------------------
    # Apply filters
    # -----------------------------------

    if selected_city and 'city' in df.columns:
        df = df[df["city"] == selected_city]

    if selected_category and 'category' in df.columns:
        df = df[df["category"] == selected_category]

    if selected_product and 'product' in df.columns:
        df = df[df["product"] == selected_product]

    # -----------------------------------
    # Check filtered data
    # -----------------------------------

    if df.empty:
        return render_template(
            "dashboard.html",

            total_sales=0,
            average_sales=0,
            total_quantity=0,
            best_product="No Data",
            top_city="No Data",

            cities=cities,
            categories=categories,
            products=products,

            selected_city=selected_city,
            selected_category=selected_category,
            selected_product=selected_product,

            preview_columns=[],
            preview_rows=[],

            product_chart=None,
            category_chart=None,
            monthly_chart=None,

            no_data=True
        )

    # -----------------------------------
    # Cleaned Data Preview
    # -----------------------------------

    preview_df = df.head(100)

    preview_columns = preview_df.columns.tolist()
    preview_rows = preview_df.values.tolist()

    # -----------------------------------
    # EDA
    # -----------------------------------

    try:
        analysis = analyze_sales_data(df)

    except Exception as e:
        app.logger.error(f"Error during dashboard analysis: {str(e)}")
        flash("Error analyzing filtered data.", "error")
        return redirect(url_for("home"))

    # -----------------------------------
    # Product Chart
    # -----------------------------------

    product_df = pd.DataFrame(
        list(analysis["product_sales"].items()),
        columns=["Product", "Sales"]
    )

    product_chart = px.bar(
        product_df,
        x="Product",
        y="Sales",
        title="Product-wise Sales"
    )

    product_chart_json = json.dumps(
        product_chart.to_dict(),
        cls=plotly.utils.PlotlyJSONEncoder
    )

    # -----------------------------------
    # Category Chart
    # -----------------------------------

    category_df = pd.DataFrame(
        list(analysis["category_sales"].items()),
        columns=["Category", "Sales"]
    )

    category_chart = px.pie(
        category_df,
        names="Category",
        values="Sales",
        title="Category-wise Sales"
    )

    category_chart_json = json.dumps(
        category_chart.to_dict(),
        cls=plotly.utils.PlotlyJSONEncoder
    )

    # -----------------------------------
    # Monthly Chart
    # -----------------------------------

    monthly_df = pd.DataFrame(
        list(analysis["monthly_sales"].items()),
        columns=["Month", "Sales"]
    )

    monthly_chart = px.line(
        monthly_df,
        x="Month",
        y="Sales",
        markers=True,
        title="Monthly Sales Trend"
    )

    monthly_chart_json = json.dumps(
        monthly_chart.to_dict(),
        cls=plotly.utils.PlotlyJSONEncoder
    )

    # -----------------------------------
    # Dashboard
    # -----------------------------------

    return render_template(
        "dashboard.html",

        total_sales=analysis["total_sales"],
        average_sales=analysis["average_sales"],
        total_quantity=analysis["total_quantity"],
        best_product=analysis["best_product"],
        top_city=analysis["top_city"],

        cities=cities,
        categories=categories,
        products=products,

        selected_city=selected_city,
        selected_category=selected_category,
        selected_product=selected_product,

        preview_columns=preview_columns,
        preview_rows=preview_rows,

        product_chart=product_chart_json,
        category_chart=category_chart_json,
        monthly_chart=monthly_chart_json,

        no_data=False
    )


# -----------------------------------
# Download Endpoints
# -----------------------------------

@app.route("/download")
def download_file():
    """
    Download the active session's dataset as CSV.
    """
    try:
        df = _get_active_dataset()

    except Exception as e:
        app.logger.error(f"Error preparing CSV download: {str(e)}")
        df = None

    if df is None:
        flash("Cleaned dataset not found. Please upload a dataset first.", "warning")
        return redirect(url_for("home"))

    import io
    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="cleaned_sales_data.csv",
        mimetype="text/csv"
    )


@app.route("/download-excel")
def download_excel():
    """
    Download the active session's dataset as Excel.
    """
    try:
        df = _get_active_dataset()

    except Exception as e:
        app.logger.error(f"Error preparing Excel download: {str(e)}")
        df = None

    if df is None:
        flash("Cleaned dataset not found. Please upload a dataset first.", "warning")
        return redirect(url_for("home"))

    try:
        import io
        output = io.BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name="cleaned_sales_data.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        app.logger.error(f"Error generating Excel file: {str(e)}")
        flash("Error generating Excel file.", "error")
        return redirect(url_for("dashboard"))


# -----------------------------------
# Chatbot API Endpoint
# -----------------------------------

@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Handle chatbot messages using Gemini and DuckDB MCP.
    """
    session_id = session.get("dataset_session_id")
    if not session_id:
        return {"success": False, "error": "No active dataset session"}, 401

    data = request.get_json()
    if not data or "message" not in data:
        return {"success": False, "error": "Message is required"}, 400

    message = data["message"]

    # Import chatbot service lazily to handle missing dependencies gracefully
    try:
        from src.chatbot_service import ChatbotService
        import asyncio

        chatbot = ChatbotService()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        answer = loop.run_until_complete(chatbot.process_chat_message(session_id, message))

        return {"success": True, "answer": answer}
    except Exception as e:
        app.logger.error(f"Error in chat endpoint: {str(e)}")
        return {"success": False, "error": str(e)}, 500


# -----------------------------------
# Error Handlers
# -----------------------------------

@app.errorhandler(413)
def request_entity_too_large(error):
    """
    Handle file size exceeded error.
    """
    max_size_mb = Config.MAX_CONTENT_LENGTH / (1024 * 1024)
    flash(f"File too large. Maximum allowed size is {max_size_mb:.0f} MB.", "error")
    return redirect(url_for("home"))


@app.errorhandler(500)
def internal_error(error):
    """
    Handle internal server errors.
    """
    app.logger.error(f"Internal server error: {str(error)}")
    flash("An internal error occurred. Please try again later.", "error")
    return redirect(url_for("home"))


# -----------------------------------
# Run Flask
# -----------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "False") == "True"

    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug
    )

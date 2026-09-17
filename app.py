from flask import Flask, render_template, request, send_file,redirect,url_for,session
import pandas as pd
import os
import plotly
import plotly.express as px
import json

from src.cleaning import clean_sales_data
from src.analysis import analyze_sales_data


app = Flask(__name__)
app.secret_key = "sales-analytics-secret-key"
# -----------------------------------
# Folder setup
# -----------------------------------

UPLOAD_FOLDER = "data/raw"
CLEANED_FOLDER = "data/cleaned"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CLEANED_FOLDER, exist_ok=True)


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

    file = request.files.get("file")

    # Check file
    if file is None or file.filename == "":
        return "No file selected"

    # Check extension
    if not (
        file.filename.lower().endswith(".csv")
        or file.filename.lower().endswith(".xlsx")
    ):
        return "Only CSV and Excel files are allowed"

    # -----------------------------------
    # Save original file
    # -----------------------------------

    file_path = os.path.join(
        UPLOAD_FOLDER,
        file.filename
    )

    file.save(file_path)

    # -----------------------------------
    # Read dataset
    # -----------------------------------

    try:

        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(file_path)

        else:
            df = pd.read_excel(file_path)

    except Exception as e:
        return f"Error while reading file: {e}"

    # -----------------------------------
    # BEFORE CLEANING information
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

    except Exception as e:
        return f"Error while cleaning data: {e}"
    
    after_rows = len(cleaned_df)
    after_columns = len(cleaned_df.columns)
    after_missing = int(cleaned_df.isnull().sum().sum())
    rows_removed = before_rows - after_rows
    
        # -----------------------------------
        # EDA
        # -----------------------------------
    try:
        analysis=analyze_sales_data(cleaned_df)
        
    except Exception as e:
        return f"Error while analyzing data: {e}"
    
    # -----------------------------------
    # Create charts
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
    # AFTER CLEANING information
    # -----------------------------------

    after_rows = len(cleaned_df)
    after_columns = len(cleaned_df.columns)

    after_duplicates = cleaned_df.duplicated().sum()

    after_missing = int(cleaned_df.isnull().sum().sum())

    # -----------------------------------
    # Save cleaned dataset
    # -----------------------------------

    cleaned_path = os.path.join(
        CLEANED_FOLDER,
        "cleaned_sales_data.csv"
    )

    cleaned_df.to_csv(
        cleaned_path,
        index=False
    )
    
    cleaning_report = {
    "before_rows": before_rows,
    "after_rows": after_rows,
    "before_columns": before_columns,
    "after_columns": after_columns,
    "duplicates": int(before_duplicates),
    "before_missing": before_missing,
    "after_missing": after_missing,
    "rows_removed": rows_removed
}
    session["cleaning_report"] = cleaning_report
    # -----------------------------------
    # Go to dashboard
    # -----------------------------------
    
    return redirect(url_for("result"))
    
    # -----------------------------------
    # Missing values after cleaning
    # -----------------------------------

    missing_values = cleaned_df.isnull().sum()

    # -----------------------------------
    # Data types after cleaning
    # -----------------------------------

    data_types = cleaned_df.dtypes.astype(str)

    # -----------------------------------
    # Preview cleaned data
    # -----------------------------------

    preview = cleaned_df.head(10)

    table = preview.to_html(
        classes="sales-table",
        index=False
    )

    # -----------------------------------
    # Send result to HTML
    # -----------------------------------

    return render_template(
    "result.html",

    filename=file.filename,

    before_rows=before_rows,
    before_columns=before_columns,
    before_duplicates=before_duplicates,
    before_missing=before_missing,

    after_rows=after_rows,
    after_columns=after_columns,
    after_duplicates=after_duplicates,
    after_missing=after_missing,

    missing_values=missing_values.to_dict(),
    data_types=data_types.to_dict(),
    table=table,

    total_sales=analysis["total_sales"],
    average_sales=analysis["average_sales"],
    total_quantity=analysis["total_quantity"],
    best_product=analysis["best_product"],
    top_city=analysis["top_city"],

    category_sales=analysis["category_sales"],
    monthly_sales=analysis["monthly_sales"],

    product_chart=product_chart_json,
    category_chart=category_chart_json,
    monthly_chart=monthly_chart_json
)

# -----------------------------------
# Download cleaned dataset
# -----------------------------------

@app.route("/result")
def result():

    report = session.get("cleaning_report")

    if not report:
        return redirect(url_for("home"))

    return render_template(
        "result.html",
        report=report
    )

@app.route("/dashboard")
def dashboard():

    cleaned_path = os.path.join(
        CLEANED_FOLDER,
        "cleaned_sales_data.csv"
    )

    if not os.path.exists(cleaned_path):
        return "Please upload a dataset first."

    # -----------------------------------
    # Load cleaned dataset
    # -----------------------------------

    df = pd.read_csv(cleaned_path)

    # Convert date
    df["order_date"] = pd.to_datetime(
        df["order_date"],
        errors="coerce"
    )

    # -----------------------------------
    # Filter options
    # -----------------------------------

    all_df = pd.read_csv(cleaned_path)

    cities = sorted(
        all_df["city"]
        .dropna()
        .unique()
        .tolist()
    )

    categories = sorted(
        all_df["category"]
        .dropna()
        .unique()
        .tolist()
    )

    products = sorted(
        all_df["product"]
        .dropna()
        .unique()
        .tolist()
    )

    # -----------------------------------
    # Get selected filters
    # -----------------------------------

    selected_city = request.args.get("city", "")
    selected_category = request.args.get("category", "")
    selected_product = request.args.get("product", "")

    # -----------------------------------
    # Apply filters
    # -----------------------------------

    if selected_city:
        df = df[df["city"] == selected_city]

    if selected_category:
        df = df[df["category"] == selected_category]

    if selected_product:
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

    preview_df = df.head(10)

    preview_columns = preview_df.columns.tolist()
    preview_rows = preview_df.values.tolist()

    # -----------------------------------
    # EDA
    # -----------------------------------

    analysis = analyze_sales_data(df)

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
@app.route("/download")
def download_file():

    cleaned_path = os.path.join(
        CLEANED_FOLDER,
        "cleaned_sales_data.csv"
    )

    if not os.path.exists(cleaned_path):
        return "Cleaned dataset not found. Please upload a dataset first."

    return send_file(
        cleaned_path,
        as_attachment=True,
        download_name="cleaned_sales_data.csv"
    )

@app.route("/download-excel")
def download_excel():

    cleaned_path = os.path.join(
        CLEANED_FOLDER,
        "cleaned_sales_data.csv"
    )

    if not os.path.exists(cleaned_path):
        return "Cleaned dataset not found. Please upload a dataset first."

    df = pd.read_csv(cleaned_path)

    excel_path = os.path.join(
        CLEANED_FOLDER,
        "cleaned_sales_data.xlsx"
    )

    df.to_excel(
        excel_path,
        index=False
    )

    return send_file(
        excel_path,
        as_attachment=True,
        download_name="cleaned_sales_data.xlsx"
    )

# -----------------------------------
# Run Flask
# -----------------------------------

if __name__ == "__main__":
    app.run(debug=True)
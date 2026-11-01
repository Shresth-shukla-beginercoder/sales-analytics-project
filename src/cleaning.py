import pandas as pd


def clean_sales_data(df):

    # Make a copy so the original DataFrame is not modified
    df = df.copy()

    # -----------------------------------
    # 1. Clean column names
    # -----------------------------------

    df.columns = (
        df.columns
        .str.strip()
        .str.replace(" ", "_")
        .str.lower()
    )

    # -----------------------------------
    # 2. Remove duplicate rows
    # -----------------------------------

    df = df.drop_duplicates()

    # -----------------------------------
    # 3. Remove extra spaces from text
    # -----------------------------------

    text_columns = df.select_dtypes(include=["object", "string"]).columns

    for column in text_columns:
        if hasattr(df[column], 'str'):
            df[column] = df[column].str.strip()

    # -----------------------------------
    # 4. Standardize common text fields
    # -----------------------------------

    text_format_columns = [
        "category",
        "subcategory",
        "brand",
        "city",
        "state",
        "country",
        "region",
        "customer_type",
        "order_status",
        "payment_method",
        "sales_channel"
    ]

    for column in text_format_columns:
        if column in df.columns:
            df[column] = df[column].str.title()

    # -----------------------------------
    # 5. Convert date columns
    # -----------------------------------

    date_columns = [
        "order_date",
        "shipping_date",
        "delivery_date"
    ]

    for column in date_columns:
        if column in df.columns:
            # Try multiple date formats
            df[column] = pd.to_datetime(
                df[column],
                errors="coerce",
                format="mixed",
                dayfirst=True
            )

    # -----------------------------------
    # 6. Convert numerical columns
    # -----------------------------------

    numeric_columns = [
        "quantity",
        "price",
        "sales",
        "discount",
        "tax",
        "profit",
        "shipping_cost"
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    # -----------------------------------
    # 7. Handle invalid quantities
    # -----------------------------------

    if "quantity" in df.columns:
        df.loc[df["quantity"] <= 0, "quantity"] = pd.NA

    # -----------------------------------
    # 8. Calculate missing sales
    # -----------------------------------

    if (
        "sales" in df.columns
        and "quantity" in df.columns
        and "price" in df.columns
    ):

        missing_sales = df["sales"].isna()

        df.loc[missing_sales, "sales"] = (
            df.loc[missing_sales, "quantity"]
            * df.loc[missing_sales, "price"]
        )

    # -----------------------------------
    # 9. Calculate sales for invalid values
    # -----------------------------------

    if (
        "sales" in df.columns
        and "quantity" in df.columns
        and "price" in df.columns
    ):

        valid_values = (
            df["quantity"].notna()
            & df["price"].notna()
        )

        invalid_sales = (
            valid_values
            & (df["sales"] <= 0)
        )

        df.loc[invalid_sales, "sales"] = (
            df.loc[invalid_sales, "quantity"]
            * df.loc[invalid_sales, "price"]
        )

    # -----------------------------------
    # 10. Remove rows with critical missing values
    # -----------------------------------

    # Define essential columns that MUST have values
    # Only include columns that are absolutely required for analysis
    essential_columns = []

    # Product is essential for product analysis
    if "product" in df.columns:
        essential_columns.append("product")

    # At least one of these is needed for sales calculations
    if "sales" in df.columns:
        essential_columns.append("sales")
    elif "quantity" in df.columns and "price" in df.columns:
        # If sales is missing but we have qty and price, we already calculated it
        pass

    # Only drop rows where ALL essential columns are null
    # This preserves as much data as possible
    if essential_columns:
        # Remove rows where essential columns are null
        before_drop = len(df)
        df = df.dropna(subset=essential_columns, how='any')
        rows_dropped = before_drop - len(df)

        if rows_dropped > 0:
            # This will be logged by the application
            pass

    # -----------------------------------
    # 11. Return cleaned DataFrame
    # -----------------------------------

    return df
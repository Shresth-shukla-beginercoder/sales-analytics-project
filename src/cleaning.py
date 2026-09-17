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

    text_columns = df.select_dtypes(include="object").columns

    for column in text_columns:
        df[column] = df[column].str.strip()

    # -----------------------------------
    # 4. Standardize category names
    # -----------------------------------

    if "category" in df.columns:
        df["category"] = df["category"].str.title()

    # -----------------------------------
    # 5. Convert dates
    # -----------------------------------

    if "order_date" in df.columns:
        df["order_date"] = pd.to_datetime(
            df["order_date"],
            errors="coerce",
            dayfirst=True
        )

    # -----------------------------------
    # 6. Convert numerical columns
    # -----------------------------------

    numeric_columns = ["quantity", "price", "sales"]

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

    if "sales" in df.columns and "quantity" in df.columns and "price" in df.columns:

        missing_sales = df["sales"].isna()

        df.loc[missing_sales, "sales"] = (
            df.loc[missing_sales, "quantity"]
            * df.loc[missing_sales, "price"]
        )

    # -----------------------------------
    # 9. Calculate sales for invalid values
    # -----------------------------------

    if "sales" in df.columns and "quantity" in df.columns and "price" in df.columns:

        valid_values = (
            df["quantity"].notna()
            & df["price"].notna()
        )

        df.loc[
            valid_values & (df["sales"] <= 0),
            "sales"
        ] = (
            df.loc[
                valid_values & (df["sales"] <= 0),
                "quantity"
            ]
            *
            df.loc[
                valid_values & (df["sales"] <= 0),
                "price"
            ]
        )

    # -----------------------------------
    # 10. Remove rows with essential missing values
    # -----------------------------------

    essential_columns = [
        "order_id",
        "order_date",
        "product",
        "category",
        "quantity",
        "price",
        "city",
        "sales"
    ]

    existing_columns = [
        column for column in essential_columns
        if column in df.columns
    ]

    df = df.dropna(subset=existing_columns)

    return df
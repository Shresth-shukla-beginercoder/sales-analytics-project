import pandas as pd


def analyze_sales_data(df):

    results = {}

    # -----------------------------
    # 1. Total Sales
    # -----------------------------

    results["total_sales"] = df["sales"].sum()

    # -----------------------------
    # 2. Average Sales
    # -----------------------------

    results["average_sales"] = df["sales"].mean()

    # -----------------------------
    # 3. Total Quantity
    # -----------------------------

    results["total_quantity"] = df["quantity"].sum()

    # -----------------------------
    # 4. Product-wise Sales
    # -----------------------------

    product_sales = (
        df.groupby("product")["sales"]
        .sum()
        .sort_values(ascending=False)
    )

    results["product_sales"] = product_sales.to_dict()

    results["best_product"] = product_sales.idxmax()

    # -----------------------------
    # 5. City-wise Sales
    # -----------------------------

    city_sales = (
        df.groupby("city")["sales"]
        .sum()
        .sort_values(ascending=False)
    )

    results["city_sales"] = city_sales.to_dict()

    results["top_city"] = city_sales.idxmax()

    # -----------------------------
    # 6. Category-wise Sales
    # -----------------------------

    category_sales = (
        df.groupby("category")["sales"]
        .sum()
        .sort_values(ascending=False)
    )

    results["category_sales"] = category_sales.to_dict()

    # -----------------------------
    # 7. Monthly Sales
    # -----------------------------

    df = df.copy()

    df["month"] = (
        df["order_date"]
        .dt.to_period("M")
        .astype(str)
    )

    monthly_sales = (
        df.groupby("month")["sales"]
        .sum()
        .sort_index()
    )

    results["monthly_sales"] = monthly_sales.to_dict()

    return results
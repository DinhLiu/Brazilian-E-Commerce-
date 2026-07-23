from pathlib import Path
import pandas as pd

def load_raw_tables(data_dir: str) -> dict[str, pd.DataFrame]:
    data_path = Path(data_dir)

    file_map = {
        "olist_customers_dataset.csv": "customers",
        "olist_geolocation_dataset.csv": "geolocation",
        "olist_order_items_dataset.csv": "order_items",
        "olist_order_payments_dataset.csv": "order_payments",
        "olist_order_reviews_dataset.csv": "order_reviews",
        "olist_orders_dataset.csv": "orders",
        "olist_products_dataset.csv": "products",
        "olist_sellers_dataset.csv": "sellers",
        "product_category_name_translation.csv": "category_translation",
    }

    date_columns = {
        "orders": [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
        "order_items": ["shipping_limit_date"],
        "order_reviews": ["review_creation_date", "review_answer_timestamp"],
    }

    tables: dict[str, pd.DataFrame] = {}

    for filename, key in file_map.items():
        file_path = data_path / filename

        if not file_path.exists():
            raise FileNotFoundError(f"Cannot found file {file_path}")

        parse_dates = date_columns.get(key, None)
        df = pd.read_csv(file_path, parse_dates=parse_dates)

        tables[key] = df

        print(f'Loaded {key}: {df.shape[0]:,} lines, {df.shape[1]:,} columns')

    return tables

def join_item_level(tables: dict) -> pd.DataFrame:
    df = tables["order_items"].copy()

    # join with orders table
    df = df.merge(
        tables["orders"],
        on="order_id",
        how="left",
    )

    # join with customers table
    df = df.merge(
        tables["customers"],
        on="customer_id",
        how="left",
    )

    # join with products table
    df = df.merge(
        tables["products"],
        on="product_id",
        how="left",
    )

    #join with sellers table
    df = df.merge(
        tables["sellers"],
        on="seller_id",
        how="left",
        suffixes=("", "_seller"),
    )   

    # join with reviews table, each review refers to an order but an order can have multiple reviews
    df = df.merge(
        tables["order_reviews"][["order_id", "review_score", "has_comment"]],
        on="order_id",
        how="left",
    )

    print(f"join_item_level: {len(df):,} line (item-level), "
            f"{df['order_id'].nunique():,} unique orders")

    return df
    

def join_order_level(item_level_df: pd.DataFrame, order_payments: pd.DataFrame) -> pd.DataFrame:

    order_df = (
        item_level_df.groupby("order_id", as_index=False)
        .agg(
            customer_id=("customer_id", "first"),
            customer_unique_id=("customer_unique_id", "first"),
            customer_state=("customer_state", "first"),
            order_status=("order_status", "first"),
            order_purchase_timestamp=("order_purchase_timestamp", "first"),
            order_approved_at=("order_approved_at", "first"),
            order_delivered_carrier_date=("order_delivered_carrier_date", "first"),
            order_delivered_customer_date=("order_delivered_customer_date", "first"),
            order_estimated_delivery_date=("order_estimated_delivery_date", "first"),
            is_invalid_timestamps=("is_invalid_timestamps", "first"),
            review_score=("review_score", "first"),
            total_price=("price", "sum"),
            total_freight=("freight_value", "sum"),
            n_items=("order_item_id", "count"),
            n_unique_products=("product_id", "nunique"),
            n_unique_sellers=("seller_id", "nunique"),
        )
    )

    payment_agg = order_payments.groupby("order_id", as_index=False).agg(
        total_payment_value=("payment_value", "sum"),
        n_payment_installments=("payment_installments", "max"),
        n_payment_methods=("payment_type", "nunique"),
    )

    order_df = order_df.merge(payment_agg, on="order_id", how="left")

    print(f"join_order_level: {len(order_df):,} orders (order-level)")

    return order_df

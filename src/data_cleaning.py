import pandas as pd


# Orders table cleaning

def check_timestamp_violations(df: pd.DataFrame) -> pd.DataFrame:
    rules = [
        ("order_purchase_timestamp", "order_approved_at"),
        ("order_approved_at", "order_delivered_carrier_date"),
        ("order_delivered_carrier_date", "order_delivered_customer_date"),
        ("order_purchase_timestamp", "order_delivered_carrier_date"),
        ("order_purchase_timestamp", "order_delivered_customer_date"),
    ]

    result = []

    for before, after in rules:
        mask_valid = df[before].notna() & df[after].notna()
        mask_violation = mask_valid & (df[after] < df[before])
        result.append({
            "rule": f'{before} <= {after}',
            "n_checked": mask_valid.sum(),
            "n_violations": mask_violation.sum(),
            "pct_violations": round(mask_violation.sum() / mask_valid.sum() * 100, 3)
                if mask_violation.sum() > 0 else 0
        })

    return pd.DataFrame(result)

def timestamp_invalid_flag(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    rules = [
        ("order_purchase_timestamp", "order_approved_at"),
        ("order_approved_at", "order_delivered_carrier_date"),
        ("order_delivered_carrier_date", "order_delivered_customer_date"),
        ("order_purchase_timestamp", "order_delivered_carrier_date"),
        ("order_purchase_timestamp", "order_delivered_customer_date"),
    ]

    violation_mask = pd.Series(False, index=df.index)
    for before, after in rules:
        mask_valid = df[before].notna() & df[after].notna()
        violation_mask |= mask_valid & (df[after] < df[before])

    df["is_invalid_timestamps"] = violation_mask

    return df

# Customers table cleaning

def clean_customers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Make sure zip code is a string
    df['customer_zip_code_prefix'] = df['customer_zip_code_prefix'].astype(str).str.zfill(5)

    # Strip blank space, Uppercase first letter for city
    df['customer_city'] = df['customer_city'].str.strip().str.title()
    df['customer_state'] = df['customer_state'].str.strip().str.upper()

    # Check valid states
    valid_states = {
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
        "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
        "SP", "SE", "TO"
    }
    invalid_states = 0
    for state in df["customer_state"]:
        if state not in valid_states: invalid_states += 1
    if invalid_states > 0:
        print(f'{invalid_states} rows have invalid state')

    return df


# Geolocation table cleaning

def get_most_common(series: pd.Series): 
    return series.value_counts().index[0] if len(series) > 0 else None

def clean_geolocation(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Make sure zip code is a string
    df['geolocation_zip_code_prefix'] = df['geolocation_zip_code_prefix'].astype(str).str.zfill(5)

    # Strip blank space, Uppercase first letter for city
    df['geolocation_city'] = df['geolocation_city'].str.strip().str.title()
    df['geolocation_state'] = df['geolocation_state'].str.strip().str.upper()

    # The country extends across South America from 5.25° N to 33.75° S, and from 34.79° W to 73.98° W longitude
    n_before = len(df)
    df = df[
        (df['geolocation_lat'].between(-33.75, 5.25) &
        df['geolocation_lng'].between(-73.98, -34.79))
    ]
    n_removed = n_before - len(df)

    if n_removed > 0:
        print(f'Remove {n_removed} coordinates outside of Brazil')

    agg_df = (
        df.groupby('geolocation_zip_code_prefix')
        .agg(
            geolocation_lat = ('geolocation_lat', "mean"),
            geolocation_lng = ('geolocation_lng', "mean"),
            geolocation_city=("geolocation_city", lambda x: get_most_common(x)),
            geolocation_state=("geolocation_state", lambda x: get_most_common(x))
        )
        .reset_index()
    )

    print(f'Aggregate {len(df):,} lines into {len(agg_df):,} distinct zip code')

    return agg_df

# Cleaning Products table

def clean_products(df: pd.DataFrame, category_translation: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df = df.rename(columns={
        'product_name_lenght': 'product_name_length',
        'product_description_lenght': 'product_description_length'
    })

    df = df.merge(
            category_translation,
            on='product_category_name',
            how='left'
        )

    # Fill NA categories with 'unknown'
    df["product_category_name_english"] = df["product_category_name_english"].fillna("unknown")
    df["product_category_name"] = df["product_category_name"].fillna("unknown")

    size_cols = [
        "product_weight_g", "product_length_cm",
        "product_height_cm", "product_width_cm"
    ]

    for col in size_cols:
        df[col] = df.groupby("product_category_name_english")[col].transform(
            lambda x: x.fillna(x.median())
        )

        print(f'Filled missing value at {col} by median value')

    return df

# Order_items table is quite clean, no unlogic price and freivalue (<= & < 0), no duplicate 

def flag_order_items_outlier(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    q1 = df['price'].quantile(0.25)
    q3 = df['price'].quantile(0.75)
    iqr = q3 - q1

    upper_bound = q3 + 1.5 * iqr

    df['is_price_outlier'] = df['price'] > upper_bound

    n_outliers = df["is_price_outlier"].sum()
    print(f'Flagged {n_outliers} lines ({n_outliers / len(df) * 100:.2f}%) has price > {upper_bound} (IQR)')

    return df

# order_payments table 
def clean_order_payments(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if (df['payment_value'] < 0).any():
        print(f'Negative payment value detected')

    # Change 'not_defined' into 'other'
    df['payment_type'] = df['payment_type'].replace("not_defined", "other")

    mask = ((df['payment_installments'] == 0) & (df['payment_type'] != 'voucher') & (df['payment_value'] > 0))
    if len(mask) > 0:
        df.loc[mask, 'payment_installments'] = 1

    return df
    

# order_reviews table

def clean_order_reviews(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    n_orders_before = df['order_id'].nunique()
    n_rows_before = len(df)

    df = (
        df.sort_values("review_answer_timestamp", ascending=False)
        .drop_duplicates(subset="order_id", keep="first")
    )

    n_removed_dup = n_rows_before - len(df)
    if n_removed_dup > 0:
        print(f'Removed {n_removed_dup} reviews with same order id (keep the lastest), -'
              f'Keeping {n_orders_before} unchanged lines')

    df["review_comment_title"] = df["review_comment_title"].fillna("")
    df["review_comment_message"] = df["review_comment_message"].fillna("")

    df["has_comment"] = df["review_comment_message"].str.strip() != ""

    return df

# Clean seller

def clean_sellers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["seller_zip_code_prefix"] = df["seller_zip_code_prefix"].astype(str).str.zfill(5)

    df["seller_city"] = df["seller_city"].str.strip().str.title()
    df["seller_state"] = df["seller_state"].str.strip().str.upper()

    valid_states = {
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
        "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
        "SP", "SE", "TO"
    }
    invalid_states = df[~df["seller_state"].isin(valid_states)]
    if len(invalid_states) > 0:
        print(f'Warning: {len(invalid_states)} lines have invalid seller_state')

    return df
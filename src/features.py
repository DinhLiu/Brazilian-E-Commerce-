import pandas as pd
import numpy as np

def add_delivery_feature(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df['is_delivered'] = df['order_delivered_customer_date'].notna()

    df["delivery_time"] = (
        df["order_delivered_customer_date"] - df["order_purchase_timestamp"]
    ).dt.days

    df["estimated_delivery_time"] = (
        df["order_estimated_delivery_date"] - df["order_purchase_timestamp"]
    ).dt.days

    df["delivery_delay"] = (
        df["order_delivered_customer_date"] - df["order_estimated_delivery_date"]
    ).dt.days

    df["is_late"] = df["delivery_delay"] > 0

    return df


def compute_rfm(df: pd.DataFrame, reference_date: pd.Timestamp | None = None) -> pd.DataFrame:
    df = df.copy()

    # ONly compute on success orders
    n_before = len(df)
    df = df[~df['order_status'].isin(['unavailable', 'canceled'])]
    n_removed = n_before - len(df)

    if n_removed > 0:
        print(f'Removed {n_removed} orders which have canceled/unavailable status out of rfm computation')

    if reference_date is None:
        reference_date = df['order_purchase_timestamp'].max() + pd.Timedelta(days=1)
    
    rfm = (
        df.groupby("customer_unique_id").agg(
            recency = ("order_purchase_timestamp", lambda x: (reference_date - x.max()).days),
            frequency = ("order_id", "nunique"),
            monetary = ("total_payment_value", "sum")
        ).reset_index()
    )

    print(f'Computed rfm for {len(rfm)} customers (customer_unique_id), '
          f'reference date: {reference_date}')

    return rfm

def add_rfm_scores(rfm_df: pd.DataFrame, n_bins: int = 5) -> pd.DataFrame:
    df = rfm_df.copy()

    # Recency Score: The smaller the ecency (newly purchased) -> the higher the score
    # qcut by rank to avoid errors when many values ​​overlap at the bin border
    df["r_score"] = pd.qcut(
        df["recency"].rank(method="first"), q=n_bins, labels=range(n_bins, 0, -1)
    ).astype(int)

    # Frequency score: rule-based as the data is clustered at F=1
    def freq_score(f):
        if f == 1:
            return 1
        elif f == 2:
            return 3
        else:
            return 5

    df["f_score"] = df["frequency"].apply(freq_score)

    # Monetary score: quantile on log-transform to avoid deviation by outlier
    df["monetary_log"] = np.log1p(df["monetary"])
    df["m_score"] = pd.qcut(
        df["monetary_log"].rank(method="first"), q=n_bins, labels=range(1, n_bins + 1)
    ).astype(int)

    df["rfm_total"] = df["r_score"] + df["f_score"] + df["m_score"]

    def segment(row):
        r, f, m = row["r_score"], row["f_score"], row["m_score"]
        if f >= 5 and r >= 4:
            return "Champions"
        elif f >= 3 and r >= 3:
            return "Loyal Customers"
        elif r >= 4 and f == 1:
            return "New Customers"
        elif r <= 2 and f >= 3:
            return "At Risk"
        elif r <= 2 and m >= 4:
            return "Cannot Lose Them"
        elif r <= 2 and f == 1:
            return "Hibernating"
        else:
            return "Need Attention"

    df["rfm_segment"] = df.apply(segment, axis=1)

    print(df["rfm_segment"].value_counts())

    return df
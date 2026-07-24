"""Load and prepare processed Olist tables for the Streamlit dashboard."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

DELAY_BINS = [-np.inf, 0, 3, 7, 14, np.inf]
DELAY_LABELS = [
    "Soon/On time",
    "Late 1-3 days",
    "Late 4-7 days",
    "Late 8-14 days",
    "Late >14 days",
]

SPEED_BINS = [-np.inf, 5, 10, 15, 20, np.inf]
SPEED_LABELS = ["<= 5 days", "6-10 days", "11-15 days", "16-20 days", ">20 days"]

SEGMENT_ORDER = [
    "Champions",
    "Loyal Customers",
    "New Customers",
    "Need Attention",
    "At Risk",
    "Cannot Lose Them",
    "Hibernating",
]

SEGMENT_COLORS = {
    "Champions": "#2E7D32",
    "Loyal Customers": "#558B2F",
    "New Customers": "#1565C0",
    "Need Attention": "#F9A825",
    "At Risk": "#EF6C00",
    "Cannot Lose Them": "#C62828",
    "Hibernating": "#78909C",
}


def _read(name: str) -> pd.DataFrame:
    path = PROCESSED / name
    if not path.exists():
        raise FileNotFoundError(f"Missing processed file: {path}")
    return pd.read_parquet(path)


@st.cache_data(show_spinner=False)
def load_orders(trend: bool = False) -> pd.DataFrame:
    name = "order_level_trend.parquet" if trend else "order_level.parquet"
    df = _read(name)
    df["order_purchase_timestamp"] = pd.to_datetime(df["order_purchase_timestamp"])
    return df


@st.cache_data(show_spinner=False)
def load_rfm() -> pd.DataFrame:
    return _read("rfm.parquet")


@st.cache_data(show_spinner=False)
def load_category_summary() -> pd.DataFrame:
    return _read("category_summary.parquet").reset_index()


@st.cache_data(show_spinner=False)
def load_category_growth() -> pd.DataFrame:
    return _read("category_growth.parquet").reset_index()


@st.cache_data(show_spinner=False)
def load_seller_summary() -> pd.DataFrame:
    return _read("seller_summary.parquet").reset_index()


@st.cache_data(show_spinner=False)
def load_risk_sellers() -> pd.DataFrame:
    return _read("risk_sellers.parquet").reset_index()


@st.cache_data(show_spinner=False)
def load_market_basket() -> pd.DataFrame:
    return _read("market_basket_rules.parquet")


@st.cache_data(show_spinner=False)
def load_item_level() -> pd.DataFrame:
    df = _read("item_level.parquet")
    for col in (
        "order_purchase_timestamp",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
        "shipping_limit_date",
    ):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df


def filter_orders(
    df: pd.DataFrame,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    states: list[str] | None = None,
) -> pd.DataFrame:
    out = df
    if start is not None:
        out = out[out["order_purchase_timestamp"] >= pd.Timestamp(start)]
    if end is not None:
        # Inclusive end-of-day
        out = out[out["order_purchase_timestamp"] < pd.Timestamp(end) + pd.Timedelta(days=1)]
    if states:
        out = out[out["customer_state"].isin(states)]
    return out


def delivered_valid(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["is_delivered"] & ~df["is_invalid_timestamps"]].copy()


def add_delay_bucket(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["delay_bucket"] = pd.cut(
        out["delivery_delay"],
        bins=DELAY_BINS,
        labels=DELAY_LABELS,
    )
    return out


def add_speed_bucket(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["speed_bucket"] = pd.cut(
        out["delivery_time"],
        bins=SPEED_BINS,
        labels=SPEED_LABELS,
    )
    return out


def segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rfm.groupby("rfm_segment", as_index=False)
        .agg(
            n_customers=("customer_unique_id", "count"),
            total_revenue=("monetary", "sum"),
            avg_monetary=("monetary", "mean"),
            avg_recency=("recency", "mean"),
            avg_frequency=("frequency", "mean"),
        )
    )
    total_customers = summary["n_customers"].sum()
    total_revenue = summary["total_revenue"].sum()
    summary["pct_customers"] = summary["n_customers"] / total_customers * 100
    summary["pct_revenue"] = summary["total_revenue"] / total_revenue * 100
    summary["rfm_segment"] = pd.Categorical(
        summary["rfm_segment"], categories=SEGMENT_ORDER, ordered=True
    )
    return summary.sort_values("rfm_segment")


def late_by_state(df: pd.DataFrame, min_orders: int = 30) -> pd.DataFrame:
    by_state = (
        df.groupby("customer_state", as_index=False)
        .agg(
            n_orders=("order_id", "count"),
            late_rate=("is_late", "mean"),
            avg_review=("review_score", "mean"),
            avg_delivery_time=("delivery_time", "mean"),
        )
    )
    return by_state[by_state["n_orders"] >= min_orders].sort_values(
        "late_rate", ascending=False
    )


def monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    tmp = df.copy()
    tmp["month"] = tmp["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
    return (
        tmp.groupby("month", as_index=False)
        .agg(
            n_orders=("order_id", "count"),
            revenue=("total_payment_value", "sum"),
            avg_review=("review_score", "mean"),
            late_rate=("is_late", "mean"),
        )
        .sort_values("month")
    )


def filter_items(
    df: pd.DataFrame,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
    states: list[str] | None = None,
) -> pd.DataFrame:
    out = df
    if start is not None:
        out = out[out["order_purchase_timestamp"] >= pd.Timestamp(start)]
    if end is not None:
        out = out[out["order_purchase_timestamp"] < pd.Timestamp(end) + pd.Timedelta(days=1)]
    if states:
        out = out[out["customer_state"].isin(states)]
    return out


def delivered_valid_items(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["order_status"] == "delivered") & ~df["is_invalid_timestamps"]].copy()


# ---------------------------------------------------------------------------
# Notebook 07 — repeat purchase drivers
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def build_first_orders() -> pd.DataFrame:
    """First order per customer labeled with eventual RFM frequency / is_repeat."""
    orders = load_orders()
    rfm = load_rfm()
    first = (
        orders.sort_values("order_purchase_timestamp")
        .drop_duplicates(subset="customer_unique_id", keep="first")
        .copy()
    )
    first = first.merge(
        rfm[["customer_unique_id", "frequency"]],
        on="customer_unique_id",
        how="left",
    )
    first["is_repeat"] = first["frequency"] >= 2
    denom = first["total_freight"] + first["total_price"]
    first["freight_share"] = np.where(denom > 0, first["total_freight"] / denom, np.nan)
    return first


def first_order_metric_compare(first_orders: pd.DataFrame) -> pd.DataFrame:
    metrics = {
        "late_rate": ("is_late", "mean"),
        "avg_review": ("review_score", "mean"),
        "freight_share": ("freight_share", "mean"),
        "avg_installments": ("n_payment_installments", "mean"),
        "avg_delivery_days": ("delivery_time", "mean"),
        "n_customers": ("customer_unique_id", "count"),
    }
    rows = []
    for is_repeat, label in [(False, "One-time"), (True, "Repeat")]:
        subset = first_orders[first_orders["is_repeat"] == is_repeat]
        row = {"group": label, "is_repeat": is_repeat}
        for name, (col, how) in metrics.items():
            row[name] = getattr(subset[col], how)() if len(subset) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def category_repeat_rates(
    item_level: pd.DataFrame,
    first_orders: pd.DataFrame,
    min_count: int = 50,
) -> pd.DataFrame:
    from statsmodels.stats.proportion import proportion_confint

    first_ids = set(first_orders["order_id"])
    items = item_level[item_level["order_id"].isin(first_ids)].copy()
    items = items.merge(
        first_orders[["order_id", "is_repeat"]],
        on="order_id",
        how="left",
    )
    rates = (
        items.groupby("product_category_name_english", as_index=False)
        .agg(repeat_rate=("is_repeat", "mean"), n_orders=("order_id", "nunique"))
    )
    # count rows used for CI (notebook used item rows / is_repeat mean * count)
    counts = (
        items.groupby("product_category_name_english")
        .agg(count=("is_repeat", "size"), mean=("is_repeat", "mean"))
        .reset_index()
    )
    rates = rates.merge(counts, on="product_category_name_english")
    rates = rates[rates["count"] >= min_count].copy()
    successes = rates["mean"].mul(rates["count"]).round().astype(int)
    ci_low, ci_high = proportion_confint(
        successes, rates["count"], method="wilson"
    )
    rates["ci_low"] = ci_low
    rates["ci_high"] = ci_high
    rates["repeat_rate"] = rates["mean"]
    return rates.sort_values("repeat_rate", ascending=False)


# ---------------------------------------------------------------------------
# Notebook 08 — ETA calibration
# ---------------------------------------------------------------------------
def add_eta_error(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["eta_error"] = out["delivery_time"] - out["estimated_delivery_time"]
    return out


def eta_by_state(df: pd.DataFrame, min_orders: int = 30) -> pd.DataFrame:
    tmp = add_eta_error(df)
    by_state = (
        tmp.groupby("customer_state", as_index=False)
        .agg(
            avg_eta_error=("eta_error", "mean"),
            late_rate=("is_late", "mean"),
            avg_review=("review_score", "mean"),
            n_orders=("order_id", "nunique"),
        )
    )
    return by_state[by_state["n_orders"] >= min_orders].sort_values(
        "avg_eta_error", ascending=False
    )


def eta_by_seller(item_level: pd.DataFrame, min_orders: int = 30) -> pd.DataFrame:
    tmp = delivered_valid_items(item_level)
    tmp["eta_error"] = (
        (tmp["order_delivered_customer_date"] - tmp["order_purchase_timestamp"]).dt.days
        - (tmp["order_estimated_delivery_date"] - tmp["order_purchase_timestamp"]).dt.days
    )
    by_seller = (
        tmp.groupby("seller_id", as_index=False)
        .agg(
            avg_eta_error=("eta_error", "mean"),
            late_rate=("eta_error", lambda s: (s > 0).mean()),
            avg_review=("review_score", "mean"),
            n_orders=("order_id", "nunique"),
        )
    )
    return by_seller[by_seller["n_orders"] >= min_orders].sort_values(
        "avg_eta_error", ascending=False
    )


def eta_risk_overlap(eta_sellers: pd.DataFrame, risk_sellers: pd.DataFrame) -> pd.DataFrame:
    return eta_sellers.merge(risk_sellers, on="seller_id", how="inner", suffixes=("_eta", "_risk"))


# ---------------------------------------------------------------------------
# Notebook 09 — seller fulfillment SLA
# ---------------------------------------------------------------------------
def prepare_sla_items(item_level: pd.DataFrame) -> pd.DataFrame:
    tmp = delivered_valid_items(item_level)
    tmp["seller_delay"] = (
        tmp["order_delivered_carrier_date"] - tmp["shipping_limit_date"]
    ).dt.days
    tmp["seller_missed_sla"] = tmp["seller_delay"] > 0
    tmp["carrier_transit_days"] = (
        tmp["order_delivered_customer_date"] - tmp["order_delivered_carrier_date"]
    ).dt.days
    tmp["estimated_transit_days"] = (
        tmp["order_estimated_delivery_date"] - tmp["shipping_limit_date"]
    ).dt.days
    tmp["carrier_delay"] = tmp["carrier_transit_days"] - tmp["estimated_transit_days"]
    tmp["is_late_overall"] = (
        tmp["order_delivered_customer_date"] > tmp["order_estimated_delivery_date"]
    )

    seller = tmp["seller_missed_sla"].fillna(False)
    carrier = (tmp["carrier_delay"] > 0).fillna(False)
    cause = np.full(len(tmp), "both", dtype=object)
    cause[seller & ~carrier] = "seller"
    cause[~seller & carrier] = "carrier"
    tmp["primary_cause"] = np.where(tmp["is_late_overall"].fillna(False), cause, pd.NA)
    return tmp


@st.cache_data(show_spinner=False)
def load_sla_items() -> pd.DataFrame:
    return prepare_sla_items(load_item_level())


def late_cause_breakdown(sla_items: pd.DataFrame) -> pd.DataFrame:
    late = sla_items[sla_items["is_late_overall"].fillna(False)]
    if late.empty:
        return pd.DataFrame(columns=["cause", "n", "share"])
    counts = late["primary_cause"].value_counts(dropna=False).rename_axis("cause").reset_index(name="n")
    counts["share"] = counts["n"] / counts["n"].sum()
    return counts


def seller_sla_summary(sla_items: pd.DataFrame, min_orders: int = 30) -> pd.DataFrame:
    deduped = sla_items.drop_duplicates(subset=["order_id", "seller_id"])
    summary = (
        deduped.groupby("seller_id", as_index=False)
        .agg(
            seller_missed_sla_rate=("seller_missed_sla", "mean"),
            avg_seller_delay=("seller_delay", "mean"),
            n_orders=("order_id", "nunique"),
        )
    )
    return summary[summary["n_orders"] >= min_orders].sort_values(
        "seller_missed_sla_rate", ascending=False
    )


def risk_sellers_with_sla(
    risk_sellers: pd.DataFrame,
    seller_sla: pd.DataFrame,
) -> pd.DataFrame:
    return risk_sellers.merge(seller_sla, on="seller_id", how="left", suffixes=("", "_sla"))


def sla_by_state(sla_items: pd.DataFrame, min_orders: int = 30) -> pd.DataFrame:
    deduped = sla_items.drop_duplicates(subset=["order_id", "seller_id"])
    by_state = (
        deduped.groupby("customer_state", as_index=False)
        .agg(
            seller_missed_sla_rate=("seller_missed_sla", "mean"),
            avg_seller_delay=("seller_delay", "mean"),
            avg_carrier_delay=("carrier_delay", "mean"),
            n_orders=("order_id", "nunique"),
        )
    )
    return by_state[by_state["n_orders"] >= min_orders].sort_values(
        "seller_missed_sla_rate", ascending=False
    )


def format_brl(value: float) -> str:
    return f"R$ {value:,.0f}"


def format_pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"

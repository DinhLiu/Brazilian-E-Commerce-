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


def format_brl(value: float) -> str:
    return f"R$ {value:,.0f}"


def format_pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"

"""Olist Analytics Dashboard — combines RFM, delivery/review, and seller/category results."""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st

_DASHBOARD_DIR = Path(__file__).resolve().parent
if str(_DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_DIR))

from loaders import (
    SEGMENT_COLORS,
    SEGMENT_ORDER,
    add_delay_bucket,
    add_eta_error,
    add_speed_bucket,
    build_first_orders,
    category_repeat_rates,
    delivered_valid,
    eta_by_seller,
    eta_by_state,
    eta_risk_overlap,
    filter_items,
    filter_orders,
    first_order_metric_compare,
    format_brl,
    format_pct,
    late_by_state,
    late_cause_breakdown,
    load_category_growth,
    load_category_summary,
    load_item_level,
    load_market_basket,
    load_orders,
    load_rfm,
    load_risk_sellers,
    load_seller_summary,
    load_sla_items,
    monthly_trend,
    risk_sellers_with_sla,
    segment_summary,
    seller_sla_summary,
    sla_by_state,
)

st.set_page_config(
    page_title="Olist Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)

PLOTLY_LAYOUT = dict(
    margin=dict(l=40, r=20, t=50, b=40),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(size=13),
)


def style_fig(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(**PLOTLY_LAYOUT, height=height)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.2)")
    return fig


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _date_bounds():
    orders = load_orders(trend=True)
    return (
        orders["order_purchase_timestamp"].min().date(),
        orders["order_purchase_timestamp"].max().date(),
        sorted(orders["customer_state"].dropna().unique().tolist()),
    )


min_date, max_date, all_states = _date_bounds()

with st.sidebar:
    st.title("Olist Analytics")
    st.caption("Customer · Delivery · Marketplace")
    st.divider()

    page = st.radio(
        "Page",
        [
            "Overview",
            "RFM Segmentation",
            "Repeat Purchase",
            "Delivery & Reviews",
            "ETA Calibration",
            "Categories & Sellers",
            "Seller Fulfillment SLA",
            "Market Basket",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.subheader("Filters")
    date_range = st.date_input(
        "Purchase date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    states = st.multiselect(
        "Customer state",
        options=all_states,
        default=[],
        placeholder="All states",
    )
    st.caption("Empty state filter = all Brazil.")


if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

orders = filter_orders(load_orders(), start_date, end_date, states or None)
orders_trend = filter_orders(load_orders(trend=True), start_date, end_date, states or None)
delivery_df = delivered_valid(orders)
items_df = filter_items(load_item_level(), start_date, end_date, states or None)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def page_overview() -> None:
    st.header("Overview")
    st.caption(
        "Platform snapshot from cleaned order-level data. "
        "Time series exclude the truncated Sep 2018 month."
    )

    n_orders = len(orders)
    revenue = orders["total_payment_value"].sum()
    n_customers = orders["customer_unique_id"].nunique()
    avg_review = orders["review_score"].mean()
    late_rate = delivery_df["is_late"].mean() if len(delivery_df) else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Orders", f"{n_orders:,}")
    c2.metric("Revenue", format_brl(revenue))
    c3.metric("Customers", f"{n_customers:,}")
    c4.metric("Avg review", f"{avg_review:.2f}" if avg_review == avg_review else "—")
    c5.metric("Late rate", format_pct(late_rate))

    st.subheader("Monthly order volume & revenue")
    trend = monthly_trend(orders_trend)
    if trend.empty:
        st.warning("No orders in the selected filters.")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=trend["month"],
            y=trend["n_orders"],
            name="Orders",
            marker_color="#1565C0",
            opacity=0.85,
            yaxis="y",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend["month"],
            y=trend["revenue"],
            name="Revenue (BRL)",
            mode="lines+markers",
            line=dict(color="#C62828", width=2),
            yaxis="y2",
        )
    )
    fig.update_layout(
        yaxis=dict(title="Orders"),
        yaxis2=dict(title="Revenue (BRL)", overlaying="y", side="right"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    st.plotly_chart(style_fig(fig, 420), width='stretch')

    left, right = st.columns(2)
    with left:
        st.subheader("Orders by state (top 15)")
        by_state = (
            orders.groupby("customer_state", as_index=False)
            .agg(n_orders=("order_id", "count"), revenue=("total_payment_value", "sum"))
            .sort_values("n_orders", ascending=False)
            .head(15)
        )
        fig = px.bar(
            by_state,
            x="n_orders",
            y="customer_state",
            orientation="h",
            labels={"n_orders": "Orders", "customer_state": "State"},
            color_discrete_sequence=["#1565C0"],
        )
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(style_fig(fig), width='stretch')

    with right:
        st.subheader("Top categories by revenue")
        cats = load_category_summary().sort_values("total_revenue", ascending=False).head(10)
        fig = px.bar(
            cats,
            x="total_revenue",
            y="product_category_name_english",
            orientation="h",
            labels={
                "total_revenue": "Revenue (BRL)",
                "product_category_name_english": "Category",
            },
            color_discrete_sequence=["#2E7D32"],
        )
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(style_fig(fig), width='stretch')

    st.info(
        "**Key platform patterns:** ~97% of customers buy once; category type predicts "
        "repeat better than first-order logistics; late deliveries cut avg review "
        "4.29 → 2.27; most lateness is carrier/transit (not seller SLA), with thin "
        "ETA buffers in the Northeast."
    )


def page_rfm() -> None:
    st.header("RFM Segmentation")
    st.caption(
        "Recency / Frequency / Monetary scores on non-canceled orders. "
        "Reference date = day after last purchase. "
        "Sidebar date/state filters apply to overview/delivery; RFM uses the saved customer table."
    )

    rfm = load_rfm()
    segments = st.multiselect(
        "Show segments",
        options=SEGMENT_ORDER,
        default=SEGMENT_ORDER,
    )
    view = rfm[rfm["rfm_segment"].isin(segments)] if segments else rfm
    summary = segment_summary(view)

    total_rev = view["monetary"].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers", f"{len(view):,}")
    c2.metric("Total monetary", format_brl(total_rev))
    c3.metric("Avg monetary", format_brl(view["monetary"].mean()) if len(view) else "—")
    one_time = (view["frequency"] == 1).mean() if len(view) else 0
    c4.metric("One-time buyers", format_pct(one_time))

    left, right = st.columns(2)
    with left:
        st.subheader("Customers by segment")
        fig = px.bar(
            summary,
            x="n_customers",
            y="rfm_segment",
            orientation="h",
            color="rfm_segment",
            color_discrete_map=SEGMENT_COLORS,
            labels={"n_customers": "Customers", "rfm_segment": "Segment"},
        )
        fig.update_layout(showlegend=False, yaxis=dict(categoryorder="array", categoryarray=SEGMENT_ORDER[::-1]))
        st.plotly_chart(style_fig(fig), width='stretch')

    with right:
        st.subheader("Revenue share by segment")
        fig = px.bar(
            summary,
            x="pct_revenue",
            y="rfm_segment",
            orientation="h",
            color="rfm_segment",
            color_discrete_map=SEGMENT_COLORS,
            labels={"pct_revenue": "% of revenue", "rfm_segment": "Segment"},
        )
        fig.update_layout(showlegend=False, yaxis=dict(categoryorder="array", categoryarray=SEGMENT_ORDER[::-1]))
        st.plotly_chart(style_fig(fig), width='stretch')

    st.subheader("Segment economics")
    display = summary.copy()
    display["pct_customers"] = display["pct_customers"].map(lambda x: f"{x:.1f}%")
    display["pct_revenue"] = display["pct_revenue"].map(lambda x: f"{x:.1f}%")
    display["total_revenue"] = display["total_revenue"].map(format_brl)
    display["avg_monetary"] = display["avg_monetary"].map(format_brl)
    display["avg_recency"] = display["avg_recency"].map(lambda x: f"{x:.0f}d")
    display["avg_frequency"] = display["avg_frequency"].map(lambda x: f"{x:.2f}")
    display = display.rename(
        columns={
            "rfm_segment": "Segment",
            "n_customers": "Customers",
            "pct_customers": "% customers",
            "total_revenue": "Revenue",
            "pct_revenue": "% revenue",
            "avg_monetary": "Avg monetary",
            "avg_recency": "Avg recency",
            "avg_frequency": "Avg frequency",
        }
    )
    st.dataframe(display, width='stretch', hide_index=True)

    st.subheader("Score distributions")
    s1, s2, s3 = st.columns(3)
    with s1:
        fig = px.histogram(view, x="r_score", nbins=5, color_discrete_sequence=["#1565C0"])
        fig.update_layout(title="R score", bargap=0.15)
        st.plotly_chart(style_fig(fig, 280), width='stretch')
    with s2:
        fig = px.histogram(view, x="f_score", nbins=5, color_discrete_sequence=["#2E7D32"])
        fig.update_layout(title="F score", bargap=0.15)
        st.plotly_chart(style_fig(fig, 280), width='stretch')
    with s3:
        fig = px.histogram(view, x="m_score", nbins=5, color_discrete_sequence=["#C62828"])
        fig.update_layout(title="M score", bargap=0.15)
        st.plotly_chart(style_fig(fig, 280), width='stretch')

    st.success(
        "**Action priority:** Cannot Lose Them (~15% of customers, ~28% of revenue) "
        "are the top win-back target. Champions are tiny but highest AOV. "
        "Hibernating is large but low value — deprioritize broad reactivation. "
        "See **Repeat Purchase** for which first-order categories convert best."
    )


def page_repeat_purchase() -> None:
    st.header("Repeat Purchase Drivers")
    st.caption(
        "First order per customer labeled by eventual RFM frequency (F≥2). "
        "Sidebar date/state filters apply to category rates via first-order location/time; "
        "repeat label is global."
    )

    first = build_first_orders()
    if states:
        first = first[first["customer_state"].isin(states)]
    # Date filter on first-purchase timestamp
    first = first[
        (first["order_purchase_timestamp"] >= pd.Timestamp(start_date))
        & (first["order_purchase_timestamp"] < pd.Timestamp(end_date) + pd.Timedelta(days=1))
    ]

    if first.empty:
        st.warning("No first orders in the selected filters.")
        return

    compare = first_order_metric_compare(first)
    baseline = first["is_repeat"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("First-order customers", f"{len(first):,}")
    c2.metric("Eventual repeat rate", format_pct(baseline))
    c3.metric("One-time", f"{(~first['is_repeat']).sum():,}")
    c4.metric("Repeat (F≥2)", f"{first['is_repeat'].sum():,}")

    st.subheader("First-order service quality: one-time vs repeat")
    metric_labels = {
        "late_rate": "Late rate",
        "avg_review": "Avg review",
        "freight_share": "Freight share",
        "avg_installments": "Avg installments",
        "avg_delivery_days": "Avg delivery days",
    }
    melted = compare.melt(
        id_vars=["group"],
        value_vars=list(metric_labels),
        var_name="metric",
        value_name="value",
    )
    melted["metric"] = melted["metric"].map(metric_labels)
    fig = px.bar(
        melted,
        x="metric",
        y="value",
        color="group",
        barmode="group",
        color_discrete_map={"One-time": "#78909C", "Repeat": "#1565C0"},
        labels={"metric": "First-order metric", "value": "Value", "group": "Outcome"},
    )
    st.plotly_chart(style_fig(fig, 400), width="stretch")
    st.caption(
        "Gaps are small — first-order late rate / review alone do not explain who returns."
    )

    st.subheader("Repeat rate by first-order category")
    min_count = st.slider("Min first-order items per category", 50, 500, 50, 25)
    rates = category_repeat_rates(load_item_level(), first, min_count=min_count)
    if rates.empty:
        st.warning("No categories meet the minimum count.")
        return

    top = rates.head(15).copy()
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=top["repeat_rate"],
            y=top["product_category_name_english"],
            orientation="h",
            marker_color="#2E7D32",
            error_x=dict(
                type="data",
                array=top["ci_high"] - top["repeat_rate"],
                arrayminus=top["repeat_rate"] - top["ci_low"],
                thickness=1.2,
                width=3,
            ),
            name="Repeat rate",
        )
    )
    fig.add_vline(
        x=baseline,
        line_dash="dash",
        line_color="#C62828",
        annotation_text=f"baseline {baseline*100:.2f}%",
    )
    fig.update_layout(
        yaxis=dict(categoryorder="array", categoryarray=top["product_category_name_english"][::-1].tolist()),
        xaxis=dict(title="Eventual repeat rate", tickformat=".0%"),
    )
    st.plotly_chart(style_fig(fig, 520), width="stretch")

    left, right = st.columns(2)
    with left:
        st.markdown("**Highest repeat categories**")
        hi = rates.head(10).copy()
        hi["repeat_rate"] = hi["repeat_rate"].map(lambda x: f"{x*100:.1f}%")
        hi["ci"] = hi.apply(lambda r: f"{r['ci_low']*100:.1f}–{r['ci_high']*100:.1f}%", axis=1)
        st.dataframe(
            hi[["product_category_name_english", "repeat_rate", "count", "ci"]].rename(
                columns={
                    "product_category_name_english": "Category",
                    "repeat_rate": "Repeat rate",
                    "count": "N",
                    "ci": "Wilson CI",
                }
            ),
            width="stretch",
            hide_index=True,
        )
    with right:
        st.markdown("**Lowest repeat categories**")
        lo = rates.sort_values("repeat_rate").head(10).copy()
        lo["repeat_rate"] = lo["repeat_rate"].map(lambda x: f"{x*100:.1f}%")
        lo["ci"] = lo.apply(lambda r: f"{r['ci_low']*100:.1f}–{r['ci_high']*100:.1f}%", axis=1)
        st.dataframe(
            lo[["product_category_name_english", "repeat_rate", "count", "ci"]].rename(
                columns={
                    "product_category_name_english": "Category",
                    "repeat_rate": "Repeat rate",
                    "count": "N",
                    "ci": "Wilson CI",
                }
            ),
            width="stretch",
            hide_index=True,
        )

    st.success(
        "**Insight:** Category type matters more than first-order logistics. "
        "Reliable high-repeat starts: home_appliances, fashion_bags_accessories, "
        "furniture_decor, bed_bath_table. Electronics / musical_instruments stay low. "
        "Target win-back by first-purchase category — don’t rely on service fixes alone."
    )


def page_delivery() -> None:
    st.header("Delivery & Reviews")
    st.caption(
        "Delivered orders with valid timestamps only. "
        "Lateness (missed ETA) hurts reviews far more than absolute delivery speed."
    )

    if delivery_df.empty:
        st.warning("No delivered orders in the selected filters.")
        return

    delayed = add_delay_bucket(delivery_df)
    ontime = delayed[~delayed["is_late"]]
    late = delayed[delayed["is_late"]]

    ontime_review = ontime["review_score"].mean()
    late_review = late["review_score"].mean() if len(late) else float("nan")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Delivered orders", f"{len(delayed):,}")
    c2.metric("Late rate", format_pct(delayed["is_late"].mean()))
    c3.metric("On-time review", f"{ontime_review:.2f}")
    c4.metric(
        "Late review",
        f"{late_review:.2f}" if late_review == late_review else "—",
        delta=f"{late_review - ontime_review:.2f}" if late_review == late_review else None,
        delta_color="inverse",
    )
    c5.metric("Avg delivery days", f"{delayed['delivery_time'].mean():.1f}")

    left, right = st.columns(2)
    with left:
        st.subheader("Review score by delay bucket")
        delay_stats = (
            delayed.groupby("delay_bucket", observed=True)["review_score"]
            .agg(mean="mean", count="count")
            .reset_index()
        )
        fig = px.bar(
            delay_stats,
            x="delay_bucket",
            y="mean",
            text=delay_stats["mean"].map(lambda x: f"{x:.2f}"),
            labels={"delay_bucket": "Delay vs ETA", "mean": "Avg review"},
            color="mean",
            color_continuous_scale="RdYlGn",
            range_color=(1.5, 4.5),
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(style_fig(fig), width='stretch')
        st.caption("Saturation around 8+ days late — further delay barely worsens reviews.")

    with right:
        st.subheader("Review vs speed (on-time only)")
        speed_df = add_speed_bucket(ontime)
        speed_stats = (
            speed_df.groupby("speed_bucket", observed=True)["review_score"]
            .agg(mean="mean", count="count")
            .reset_index()
        )
        fig = px.bar(
            speed_stats,
            x="speed_bucket",
            y="mean",
            text=speed_stats["mean"].map(lambda x: f"{x:.2f}"),
            labels={"speed_bucket": "Delivery time", "mean": "Avg review"},
            color_discrete_sequence=["#1565C0"],
        )
        fig.update_traces(textposition="outside")
        fig.update_yaxes(range=[3.5, 4.6])
        st.plotly_chart(style_fig(fig), width='stretch')
        st.caption("Expectation violation (lateness) >> absolute wait time.")

    st.subheader("Late rate vs review by state")
    min_orders = st.slider("Min orders per state", 30, 500, 30, 10)
    state_stats = late_by_state(delayed, min_orders=min_orders)
    if state_stats.empty:
        st.warning("No states meet the minimum order threshold.")
        return

    corr = state_stats[["late_rate", "avg_review"]].corr().iloc[0, 1]
    fig = px.scatter(
        state_stats,
        x="late_rate",
        y="avg_review",
        size="n_orders",
        text="customer_state",
        labels={
            "late_rate": "Late rate",
            "avg_review": "Avg review",
            "n_orders": "Orders",
        },
        color="late_rate",
        color_continuous_scale="YlOrRd",
    )
    fig.update_traces(textposition="top center")
    fig.update_layout(
        title=f"State-level correlation(late_rate, avg_review) = {corr:.3f}",
        xaxis_tickformat=".0%",
    )
    st.plotly_chart(style_fig(fig, 460), width='stretch')

    st.subheader("Highest late-rate states")
    top_late = state_stats.head(10).copy()
    top_late["late_rate"] = top_late["late_rate"].map(lambda x: f"{x*100:.1f}%")
    top_late["avg_review"] = top_late["avg_review"].map(lambda x: f"{x:.2f}")
    top_late["avg_delivery_time"] = top_late["avg_delivery_time"].map(lambda x: f"{x:.1f}")
    st.dataframe(
        top_late.rename(
            columns={
                "customer_state": "State",
                "n_orders": "Orders",
                "late_rate": "Late rate",
                "avg_review": "Avg review",
                "avg_delivery_time": "Avg delivery days",
            }
        ),
        width='stretch',
        hide_index=True,
    )

    st.warning(
        "**Ops focus:** Northeast cluster (AL, MA, SE, PI, CE) shows the highest late rates "
        "and weakest reviews. Treat 7–8 day delay as an early-warning KPI for proactive outreach. "
        "See **ETA Calibration** for buffer gaps and **Seller Fulfillment SLA** for cause split."
    )


def page_eta_calibration() -> None:
    st.header("ETA Calibration")
    st.caption(
        "eta_error = delivery_time − estimated_delivery_time (days). "
        "Negative = conservative buffer; positive = over-optimistic ETA. "
        "Uses delivered orders with valid timestamps."
    )

    if delivery_df.empty:
        st.warning("No delivered orders in the selected filters.")
        return

    with_err = add_eta_error(delivery_df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Orders", f"{len(with_err):,}")
    c2.metric("Mean ETA error", f"{with_err['eta_error'].mean():.1f}d")
    c3.metric("Median ETA error", f"{with_err['eta_error'].median():.0f}d")
    c4.metric("Late rate", format_pct(with_err["is_late"].mean()))

    min_orders = st.slider("Min orders (state/seller)", 30, 200, 30, 10, key="eta_min")

    state_eta = eta_by_state(delivery_df, min_orders=min_orders)
    if state_eta.empty:
        st.warning("No states meet the minimum order threshold.")
        return

    corr_late = state_eta[["avg_eta_error", "late_rate"]].corr().iloc[0, 1]
    corr_rev = state_eta[["avg_eta_error", "avg_review"]].corr().iloc[0, 1]

    left, right = st.columns(2)
    with left:
        st.subheader("ETA error vs late rate (by state)")
        fig = px.scatter(
            state_eta,
            x="avg_eta_error",
            y="late_rate",
            size="n_orders",
            text="customer_state",
            labels={
                "avg_eta_error": "Avg ETA error (days)",
                "late_rate": "Late rate",
                "n_orders": "Orders",
            },
            color="avg_eta_error",
            color_continuous_scale="YlOrRd",
        )
        fig.update_traces(textposition="top center")
        fig.update_layout(
            title=f"corr = {corr_late:.3f}",
            yaxis_tickformat=".0%",
        )
        st.plotly_chart(style_fig(fig, 420), width="stretch")

    with right:
        st.subheader("ETA error vs avg review (by state)")
        fig = px.scatter(
            state_eta,
            x="avg_eta_error",
            y="avg_review",
            size="n_orders",
            text="customer_state",
            labels={
                "avg_eta_error": "Avg ETA error (days)",
                "avg_review": "Avg review",
                "n_orders": "Orders",
            },
            color="avg_review",
            color_continuous_scale="RdYlGn",
        )
        fig.update_traces(textposition="top center")
        fig.update_layout(title=f"corr = {corr_rev:.3f}")
        st.plotly_chart(style_fig(fig, 420), width="stretch")

    st.subheader("Thinnest ETA buffers by state")
    thin = state_eta.head(10).copy()
    thin["avg_eta_error"] = thin["avg_eta_error"].map(lambda x: f"{x:.2f}")
    thin["late_rate"] = thin["late_rate"].map(lambda x: f"{x*100:.1f}%")
    thin["avg_review"] = thin["avg_review"].map(lambda x: f"{x:.2f}")
    st.dataframe(
        thin.rename(
            columns={
                "customer_state": "State",
                "avg_eta_error": "Avg ETA error",
                "late_rate": "Late rate",
                "avg_review": "Avg review",
                "n_orders": "Orders",
            }
        ),
        width="stretch",
        hide_index=True,
    )

    st.subheader("Sellers with least ETA buffer")
    seller_eta = eta_by_seller(items_df, min_orders=min_orders)
    top_sellers = seller_eta.head(15).copy()
    top_sellers["seller_short"] = top_sellers["seller_id"].str[:14] + "…"
    fig = px.bar(
        top_sellers,
        x="avg_eta_error",
        y="seller_short",
        orientation="h",
        color="late_rate",
        color_continuous_scale="YlOrRd",
        hover_data={"seller_id": True, "avg_review": ":.2f", "n_orders": True},
        labels={
            "avg_eta_error": "Avg ETA error (days)",
            "seller_short": "Seller",
            "late_rate": "Late rate",
        },
    )
    fig.update_layout(yaxis=dict(categoryorder="total ascending"))
    st.plotly_chart(style_fig(fig, 480), width="stretch")

    risk = load_risk_sellers()
    overlap = eta_risk_overlap(seller_eta, risk)
    st.subheader(f"Risk sellers ∩ ETA table ({len(overlap)} of {len(risk)})")
    if not overlap.empty:
        ov = overlap.sort_values("avg_eta_error", ascending=False).copy()
        ov["seller_short"] = ov["seller_id"].str[:16] + "…"
        display = pd.DataFrame({
            "Seller": ov["seller_short"],
            "Avg ETA error": ov["avg_eta_error"].map(lambda x: f"{x:.2f}"),
            "Late rate": ov["late_rate"].map(lambda x: f"{x*100:.1f}%"),
            "Avg review": ov["avg_review_risk"].map(lambda x: f"{x:.2f}"),
            "Revenue": ov["total_revenue"].map(format_brl),
            "Orders": ov["n_orders_risk"],
        })
        st.dataframe(display, width="stretch", hide_index=True)

    st.warning(
        "**Action:** Platform ETA is conservative overall (median ≈ −12d), but Northeast "
        "states (AL, MA, SE, CE, BA, PI) have thinner buffers and high late rates. "
        "Widening ETA promises there is cheaper than rebuilding logistics. "
        "Also tighten promises for sellers with near-zero/positive avg ETA error."
    )


def page_categories_sellers() -> None:
    st.header("Categories & Sellers")
    st.caption(
        "Item-level revenue (sum of `price`) for delivered, valid-timestamp orders. "
        "Seller table keeps sellers with ≥10 orders."
    )

    cats = load_category_summary().sort_values("total_revenue", ascending=False)
    growth = load_category_growth().copy()
    sellers = load_seller_summary().sort_values("total_revenue", ascending=False)
    risk = load_risk_sellers().sort_values("total_revenue", ascending=False)

    top_n = st.slider("Top N categories", 5, 30, 15)

    left, right = st.columns(2)
    with left:
        st.subheader(f"Top {top_n} categories by revenue")
        top_cats = cats.head(top_n)
        fig = px.bar(
            top_cats,
            x="total_revenue",
            y="product_category_name_english",
            orientation="h",
            labels={
                "total_revenue": "Revenue (BRL)",
                "product_category_name_english": "Category",
            },
            color_discrete_sequence=["#2E7D32"],
        )
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(style_fig(fig, 480), width='stretch')

    with right:
        st.subheader("Revenue vs growth (half-period split)")
        # Match notebook: keep categories with first-half revenue > 100
        g = growth[growth["revenue_first"] > 100].copy()
        # Cap extreme growth for readable axes (artifact categories still listed in table)
        g["growth_plot"] = g["growth_rate"].clip(-1, 5)
        med_rev = g["total_revenue"].median()
        med_growth = g["growth_rate"].median()
        fig = px.scatter(
            g,
            x="total_revenue",
            y="growth_plot",
            hover_name="product_category_name_english",
            hover_data={"growth_rate": ":.1%", "total_revenue": ":,.0f", "growth_plot": False},
            labels={
                "total_revenue": "Total revenue (BRL)",
                "growth_plot": "Growth rate (clipped)",
            },
            color_discrete_sequence=["#1565C0"],
        )
        fig.add_vline(x=med_rev, line_dash="dash", line_color="#78909C")
        fig.add_hline(y=med_growth, line_dash="dash", line_color="#78909C")
        st.plotly_chart(style_fig(fig, 480), width='stretch')
        st.caption(
            f"Dashed lines = medians (revenue {format_brl(med_rev)}, "
            f"growth {med_growth*100:.1f}%). Y clipped at 500% for readability."
        )

    st.subheader("Fastest-growing categories (first-half revenue > 100)")
    grow_table = (
        growth[growth["revenue_first"] > 100]
        .sort_values("growth_rate", ascending=False)
        .head(15)
        .copy()
    )
    grow_table["growth_rate"] = grow_table["growth_rate"].map(lambda x: f"{x*100:.0f}%")
    for col in ("revenue_first", "revenue_second", "total_revenue"):
        grow_table[col] = grow_table[col].map(format_brl)
    st.dataframe(
        grow_table.rename(
            columns={
                "product_category_name_english": "Category",
                "revenue_first": "1st half revenue",
                "revenue_second": "2nd half revenue",
                "growth_rate": "Growth",
                "total_revenue": "Total revenue",
            }
        ),
        width='stretch',
        hide_index=True,
    )

    st.divider()
    st.subheader("Seller performance")
    s1, s2 = st.columns(2)
    with s1:
        st.markdown("**Top sellers by revenue**")
        top_sellers = sellers.head(15).copy()
        top_sellers["seller_short"] = top_sellers["seller_id"].str[:12] + "…"
        fig = px.bar(
            top_sellers,
            x="total_revenue",
            y="seller_short",
            orientation="h",
            hover_data={"seller_id": True, "avg_review": ":.2f", "n_orders": True},
            labels={"total_revenue": "Revenue (BRL)", "seller_short": "Seller"},
            color="avg_review",
            color_continuous_scale="RdYlGn",
            range_color=(3, 5),
        )
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(style_fig(fig, 480), width='stretch')

    with s2:
        st.markdown("**Risk sellers** — top-quartile revenue & avg review < 3.5")
        st.metric("Flagged sellers", f"{len(risk):,}")
        sla_summary = seller_sla_summary(load_sla_items(), min_orders=30)
        risk_sla = risk_sellers_with_sla(risk, sla_summary).sort_values(
            "seller_missed_sla_rate", ascending=False
        )
        risk_view = risk_sla.copy()
        risk_view["seller_id"] = risk_view["seller_id"].str[:14] + "…"
        risk_view["total_revenue"] = risk_view["total_revenue"].map(format_brl)
        risk_view["avg_review"] = risk_view["avg_review"].map(lambda x: f"{x:.2f}")
        risk_view["seller_missed_sla_rate"] = risk_view["seller_missed_sla_rate"].map(
            lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—"
        )
        st.dataframe(
            risk_view[
                ["seller_id", "total_revenue", "n_orders", "avg_review", "seller_missed_sla_rate"]
            ].rename(
                columns={
                    "seller_id": "Seller",
                    "total_revenue": "Revenue",
                    "n_orders": "Orders",
                    "avg_review": "Avg review",
                    "seller_missed_sla_rate": "SLA miss",
                }
            ),
            width="stretch",
            hide_index=True,
            height=420,
        )

    st.error(
        "Audit high-revenue / low-review sellers before scaling volume. "
        "SLA miss rates split fulfillment offenders from quality-only issues — "
        "see **Seller Fulfillment SLA** (e.g. `54965bbe…` high SLA miss vs "
        "`7c67e1448b…` ships early but weak reviews)."
    )


def page_seller_sla() -> None:
    st.header("Seller Fulfillment SLA")
    st.caption(
        "Seller stage: handoff after shipping_limit_date. "
        "Carrier stage: transit vs remaining ETA. "
        "Primary cause attributed on late items only."
    )

    sla_all = load_sla_items()
    sla = filter_items(sla_all, start_date, end_date, states or None)
    if sla.empty:
        st.warning("No delivered items in the selected filters.")
        return

    causes = late_cause_breakdown(sla)
    miss_rate = sla["seller_missed_sla"].mean()
    late_rate = sla["is_late_overall"].mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Delivered items", f"{len(sla):,}")
    c2.metric("Seller SLA miss", format_pct(miss_rate))
    c3.metric("Late vs ETA", format_pct(late_rate))
    c4.metric("Median seller delay", f"{sla['seller_delay'].median():.0f}d")

    left, right = st.columns(2)
    with left:
        st.subheader("Primary cause of late deliveries")
        if causes.empty:
            st.info("No late items in filter.")
        else:
            fig = px.pie(
                causes,
                names="cause",
                values="share",
                color="cause",
                color_discrete_map={
                    "carrier": "#1565C0",
                    "seller": "#C62828",
                    "both": "#F9A825",
                },
                hole=0.35,
            )
            fig.update_traces(textinfo="label+percent")
            st.plotly_chart(style_fig(fig, 360), width="stretch")
            st.caption("Platform-wide, most lateness is carrier/transit — not seller handoff.")

    with right:
        st.subheader("Seller SLA miss by state")
        min_orders = st.slider("Min orders per state", 30, 200, 30, 10, key="sla_state_min")
        state_sla = sla_by_state(sla, min_orders=min_orders)
        if state_sla.empty:
            st.warning("No states meet the threshold.")
        else:
            fig = px.scatter(
                state_sla,
                x="seller_missed_sla_rate",
                y="avg_carrier_delay",
                size="n_orders",
                text="customer_state",
                labels={
                    "seller_missed_sla_rate": "Seller SLA miss rate",
                    "avg_carrier_delay": "Avg carrier delay (days)",
                    "n_orders": "Orders",
                },
                color="seller_missed_sla_rate",
                color_continuous_scale="YlOrRd",
            )
            fig.update_traces(textposition="top center")
            fig.update_layout(xaxis_tickformat=".0%")
            st.plotly_chart(style_fig(fig, 360), width="stretch")
            st.caption(
                "SLA miss is fairly flat by state (~5–6%); Northeast lateness is not a "
                "seller-prep bottleneck."
            )

    st.subheader("Risk sellers by SLA miss rate")
    min_seller = st.slider("Min orders per seller (SLA sample)", 30, 100, 30, 10, key="sla_seller_min")
    seller_sla = seller_sla_summary(sla, min_orders=min_seller)
    risk = load_risk_sellers()
    risk_sla = risk_sellers_with_sla(risk, seller_sla).sort_values(
        "seller_missed_sla_rate", ascending=False
    )

    view = risk_sla.copy()
    view["seller_short"] = view["seller_id"].str[:16] + "…"
    fig = px.bar(
        view.dropna(subset=["seller_missed_sla_rate"]).head(18),
        x="seller_missed_sla_rate",
        y="seller_short",
        orientation="h",
        color="avg_review",
        color_continuous_scale="RdYlGn",
        range_color=(2.5, 4),
        hover_data={"seller_id": True, "total_revenue": ":,.0f", "n_orders": True},
        labels={
            "seller_missed_sla_rate": "SLA miss rate",
            "seller_short": "Seller",
            "avg_review": "Avg review",
        },
    )
    fig.update_layout(
        yaxis=dict(categoryorder="total ascending"),
        xaxis_tickformat=".0%",
    )
    st.plotly_chart(style_fig(fig, 480), width="stretch")

    table = risk_sla.copy()
    table["seller_id"] = table["seller_id"].str[:16] + "…"
    table["total_revenue"] = table["total_revenue"].map(format_brl)
    table["avg_review"] = table["avg_review"].map(lambda x: f"{x:.2f}")
    table["seller_missed_sla_rate"] = table["seller_missed_sla_rate"].map(
        lambda x: f"{x*100:.1f}%" if pd.notna(x) else "n<30"
    )
    table["avg_seller_delay"] = table["avg_seller_delay"].map(
        lambda x: f"{x:.2f}" if pd.notna(x) else "—"
    )
    st.dataframe(
        table[
            [
                "seller_id",
                "total_revenue",
                "n_orders",
                "avg_review",
                "seller_missed_sla_rate",
                "avg_seller_delay",
            ]
        ].rename(
            columns={
                "seller_id": "Seller",
                "total_revenue": "Revenue",
                "n_orders": "Orders",
                "avg_review": "Avg review",
                "seller_missed_sla_rate": "SLA miss",
                "avg_seller_delay": "Avg seller delay",
            }
        ),
        width="stretch",
        hide_index=True,
    )

    st.error(
        "**Insight:** ~78% of late items are carrier-only; seller SLA miss is only ~4.7% overall. "
        "Split risk sellers: fulfillment offenders (`54965bbe…`, `88460e8e…`, `a7f13822…`) vs "
        "quality issues that ship on time (`7c67e1448b…`). NE delay → transit + ETA, not seller prep."
    )


def page_market_basket() -> None:
    st.header("Market Basket")
    st.caption(
        "Association rules on multi-category orders only. "
        "Most Olist orders are single-intent purchases."
    )

    rules = load_market_basket()
    c1, c2, c3 = st.columns(3)
    c1.metric("Association rules", f"{len(rules):,}")
    c2.metric("Strongest lift", f"{rules['lift'].max():.2f}")
    c3.metric("Support (top rule)", f"{rules['support'].max()*100:.2f}%")

    display = rules.copy()
    display["support"] = display["support"].map(lambda x: f"{x*100:.2f}%")
    display["confidence"] = display["confidence"].map(lambda x: f"{x*100:.1f}%")
    display["lift"] = display["lift"].map(lambda x: f"{x:.2f}")
    st.dataframe(
        display.rename(
            columns={
                "antecedents": "Antecedent",
                "consequents": "Consequent",
                "support": "Support",
                "support_count": "Support count",
                "confidence": "Confidence",
                "lift": "Lift",
            }
        ),
        width='stretch',
        hide_index=True,
    )

    st.info(
        "Only `home_confort` ↔ `bed_bath_table` clears the support threshold "
        "(lift ≈ 3.0, n = 43). Treat as directional, not a platform-wide pattern — "
        "aligned with RFM (≈97% one-time buyers) and single-product baskets."
    )


PAGES = {
    "Overview": page_overview,
    "RFM Segmentation": page_rfm,
    "Repeat Purchase": page_repeat_purchase,
    "Delivery & Reviews": page_delivery,
    "ETA Calibration": page_eta_calibration,
    "Categories & Sellers": page_categories_sellers,
    "Seller Fulfillment SLA": page_seller_sla,
    "Market Basket": page_market_basket,
}

PAGES[page]()

import streamlit as st
from snowflake.snowpark.context import get_active_session
import altair as alt
import pandas as pd
from datetime import date

st.set_page_config(page_title="Risk Exposure Dashboard", page_icon="🏦", layout="wide")

ASN_GREEN = "#00A651"
ASN_DARK = "#004D25"
ASN_LIGHT = "#E6F7ED"

st.markdown(f"""
<style>
[data-testid="stMetricValue"] {{ font-size: 1.8rem; color: {ASN_GREEN}; }}
h1, h2, h3 {{ color: {ASN_DARK}; }}
[data-testid="stSidebar"] {{ background-color: {ASN_LIGHT}; }}
div[data-testid="stMetricLabel"] {{ font-weight: 600; }}
</style>
""", unsafe_allow_html=True)

session = get_active_session()

st.title("🏦 Risk Exposure Dashboard")
st.caption(f"ASN Bank — {date.today().strftime('%d %B %Y')}")

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/ASN_Bank_logo.svg/200px-ASN_Bank_logo.svg.png", width=160)
    st.markdown("---")
    st.subheader("Filters")

    region_options = ["All", "AMERICAS", "EMEA", "APAC"]
    selected_region = st.selectbox("Region", region_options)

    severity_options = ["All", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    selected_severity = st.selectbox("Severity", severity_options)

    event_type_options = ["All", "CREDIT", "MARKET", "OPERATIONAL", "LIQUIDITY", "COUNTERPARTY"]
    selected_event_type = st.selectbox("Event Type", event_type_options)


@st.cache_data(ttl=60)
def load_summary():
    return session.sql("""
        SELECT event_type, severity, region, month,
               event_count, total_exposure, avg_risk_score, open_events
        FROM risk_hol.analytics.risk_summary
        ORDER BY month DESC
    """).to_pandas()


df = load_summary()

if selected_region != "All":
    df = df[df["REGION"] == selected_region]
if selected_severity != "All":
    df = df[df["SEVERITY"] == selected_severity]
if selected_event_type != "All":
    df = df[df["EVENT_TYPE"] == selected_event_type]

total_events = int(df["EVENT_COUNT"].sum())
total_exposure = float(df["TOTAL_EXPOSURE"].sum())
avg_risk = float(df["AVG_RISK_SCORE"].mean()) if len(df) > 0 else 0
open_events = int(df["OPEN_EVENTS"].sum())

if total_exposure >= 1_000_000_000:
    exposure_str = f"${total_exposure / 1_000_000_000:.1f}B"
elif total_exposure >= 1_000_000:
    exposure_str = f"${total_exposure / 1_000_000:.1f}M"
else:
    exposure_str = f"${total_exposure:,.0f}"

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Events", f"{total_events:,}")
k2.metric("Total Exposure", exposure_str)
k3.metric("Avg Risk Score", f"{avg_risk:.1f}")
k4.metric("Open Events", f"{open_events:,}")

st.divider()

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Total Exposure by Event Type")
    chart_type = df.groupby("EVENT_TYPE")["TOTAL_EXPOSURE"].sum().reset_index()
    bar = alt.Chart(chart_type).mark_bar(color=ASN_GREEN).encode(
        x=alt.X("TOTAL_EXPOSURE:Q", title="Total Exposure ($)"),
        y=alt.Y("EVENT_TYPE:N", sort="-x", title=""),
        tooltip=["EVENT_TYPE", "TOTAL_EXPOSURE"]
    ).properties(height=300)
    st.altair_chart(bar, use_container_width=True)

with col_right:
    st.subheader("Event Count by Month")
    monthly = df.groupby("MONTH")["EVENT_COUNT"].sum().reset_index()
    line = alt.Chart(monthly).mark_line(
        point=True, strokeWidth=2, color=ASN_GREEN
    ).encode(
        x=alt.X("MONTH:T", title="Month"),
        y=alt.Y("EVENT_COUNT:Q", title="Event Count"),
        tooltip=["MONTH:T", "EVENT_COUNT:Q"]
    ).properties(height=300)
    st.altair_chart(line, use_container_width=True)

st.divider()

st.subheader("Event Count by Severity and Region")
heatmap_data = df.groupby(["SEVERITY", "REGION"])["EVENT_COUNT"].sum().reset_index()
severity_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
heatmap = alt.Chart(heatmap_data).mark_rect().encode(
    x=alt.X("REGION:N", title="Region"),
    y=alt.Y("SEVERITY:N", sort=severity_order, title="Severity"),
    color=alt.Color("EVENT_COUNT:Q", scale=alt.Scale(scheme="greens"), title="Events"),
    tooltip=["SEVERITY", "REGION", "EVENT_COUNT"]
).properties(height=250)
st.altair_chart(heatmap, use_container_width=True)

st.divider()

st.subheader("Filtered Data")
st.dataframe(df, use_container_width=True)
st.caption("Data is synthetic and for demonstration purposes only. | ASN Bank — Duurzaam bankieren.")

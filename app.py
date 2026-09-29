"""Streamlit app: list a company's processes, get a prioritised AI roadmap."""
import altair as alt
import pandas as pd
import streamlit as st

from prioritizer.scoring import AUTOMATION_POTENTIAL, Thresholds, report, score

st.set_page_config(page_title="AI Use-Case Prioritizer", layout="wide")
st.title("AI Use-Case Prioritizer")
st.caption(
    "The first question in every AI project: where should we start? "
    "List the processes, rate them, and get a value × feasibility matrix with payback estimates."
)

company = st.text_input("Company", "Sample distribution company (200 employees)")

st.subheader("1. Processes")
st.write("Ratings are 1 (low) to 5 (high). Edit the table or add rows.")
processes = st.data_editor(
    pd.read_csv("data/sample_processes.csv"),
    num_rows="dynamic",
    width="stretch",
    column_config={
        "ai_pattern": st.column_config.SelectboxColumn("AI pattern", options=list(AUTOMATION_POTENTIAL)),
        "hourly_cost": st.column_config.NumberColumn("Hourly cost ($)", min_value=0),
        "error_cost_per_month": st.column_config.NumberColumn("Error cost / month ($)", min_value=0),
        "data_readiness": st.column_config.NumberColumn("Data readiness", min_value=1, max_value=5),
        "standardisation": st.column_config.NumberColumn("Standardisation", min_value=1, max_value=5),
        "risk_if_wrong": st.column_config.NumberColumn("Risk if AI is wrong", min_value=1, max_value=5),
    },
)

with st.sidebar:
    st.header("Thresholds")
    impact_t = st.slider("Impact threshold", 0, 100, 50)
    feas_t = st.slider("Feasibility threshold", 0, 100, 60)
    st.header("Assumptions")
    st.write("Share of process cost AI can take over:")
    st.table(pd.Series(AUTOMATION_POTENTIAL, name="potential").map("{:.0%}".format))

processes = processes.dropna(subset=["process", "ai_pattern"])
if processes.empty:
    st.info("Add at least one process.")
    st.stop()

scored = score(processes, Thresholds(impact=impact_t, feasibility=feas_t))

st.subheader("2. Prioritisation matrix")
c1, c2, c3 = st.columns(3)
c1.metric("Addressable value / year", f"${scored['annual_value'].sum():,.0f}")
c2.metric("Quick wins", int((scored["priority"] == "Quick win").sum()))
wins = scored[scored["priority"] == "Quick win"]
c3.metric("Quick-win value / year", f"${wins['annual_value'].sum():,.0f}")

points = alt.Chart(scored).mark_circle(opacity=0.85).encode(
    x=alt.X("feasibility_score", title="Feasibility (0-100)", scale=alt.Scale(domain=[0, 115])),
    y=alt.Y("impact_score", title="Impact (0-100)", scale=alt.Scale(domain=[0, 105])),
    size=alt.Size("annual_value", title="Value / year", legend=None, scale=alt.Scale(range=[80, 1200])),
    color=alt.Color(
        "priority", title="Priority",
        scale=alt.Scale(
            domain=["Quick win", "Strategic bet", "Low-hanging fruit", "Deprioritise"],
            range=["#1a7f37", "#2a5bd7", "#bf8700", "#9aa0a6"],
        ),
        legend=alt.Legend(orient="bottom"),
    ),
    tooltip=["process", "department", "ai_pattern", alt.Tooltip("annual_value", format="$,.0f"), "payback_months"],
)
labels = points.mark_text(align="left", dx=12, fontSize=11, color="#444").encode(text="process", size=alt.value(11), color=alt.value("#444"))
rules = alt.Chart(pd.DataFrame({"x": [feas_t], "y": [impact_t]}))
lines = rules.mark_rule(strokeDash=[4, 4], color="gray").encode(x="x") + rules.mark_rule(strokeDash=[4, 4], color="gray").encode(y="y")
st.altair_chart((points + labels + lines).properties(height=460), width="stretch")

st.subheader("3. Ranked roadmap")
st.dataframe(
    scored[["process", "department", "ai_pattern", "priority", "annual_value", "impact_score", "feasibility_score", "payback_months"]],
    width="stretch", hide_index=True,
    column_config={"annual_value": st.column_config.NumberColumn("Value / year", format="$%d")},
)

md = report(scored, company)
st.download_button("Download report (Markdown)", md, "ai_roadmap.md")
with st.expander("Preview report"):
    st.markdown(md)

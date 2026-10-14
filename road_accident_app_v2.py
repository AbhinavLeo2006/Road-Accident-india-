import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Road Accidents in India", page_icon="🚦", layout="wide")

#blinking button CSS _ Pasted here 
st.markdown("""
<style>
@keyframe blink {
    0% , 100% { opacity: 1; }
    50% { opacity: 0; 3; }
}
div.stButton > button {
    animation: blink 1s infinite;
    background-color: #dc2626;
    color: white;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)
    
    # Consistent red theme across Streamlit widgets and Plotly charts.
px.defaults.color_discrete_sequence = ["#b91c1c", "#ef4444", "#7f1d1d", "#f87171", "#991b1b"]
px.defaults.color_continuous_scale = "Reds"
st.markdown("""
<style>
    :root { --primary-color: #b91c1c; }
    [data-testid="stAppViewContainer"] { border-top: 5px solid #b91c1c; }
    [data-testid="stSidebar"] { border-right: 1px solid #fecaca; }
    h1, h2, h3 { color: #991b1b; }
    div.stDownloadButton > button { border-color: #b91c1c; color: #991b1b; }
    div.stDownloadButton > button:hover { background: #b91c1c; color: white; }
</style>
""", unsafe_allow_html=True)

STATES_CSV = "states_2020_2024_clean.csv"
VIOLATIONS_CSV = "violations_2023_2024_clean.csv"
GEOJSON = "india_states.geojson"
YEARS = [2020, 2021, 2022, 2023, 2024]

# ---------------------------------------------------------------
# Load data (clear message if a file is missing)
# ---------------------------------------------------------------
folder = Path(__file__).parent
for name in (STATES_CSV, VIOLATIONS_CSV, GEOJSON):
    if not (folder / name).exists():
        st.error(f"File not found: {folder / name}. Put {name} in the same folder as this script.")
        st.stop()


@st.cache_data
def load(name):
    return pd.read_csv(folder / name)


@st.cache_data
def load_geo():
    with open(folder /  GEOJSON, encoding="utf-8") as f:
        return json.load(f)


df = load(STATES_CSV)
vio = load(VIOLATIONS_CSV)
geo = load_geo()

# One row per state per year, for line charts
long_df = (
    df.melt(id_vars="State", value_vars=[f"Acc_{y}" for y in YEARS],
            var_name="Year", value_name="Accidents")
    .assign(Year=lambda d: d["Year"].str[-4:].astype(int))
    .merge(
        df.melt(id_vars="State", value_vars=[f"Killed_{y}" for y in YEARS],
                var_name="Year", value_name="Killed")
        .assign(Year=lambda d: d["Year"].str[-4:].astype(int)),
        on=["State", "Year"],
    )
)

# State names in our data -> names used in the map file
NAME_MAP = {
    "Andaman and Nicobar Islands": ["Andaman & Nicobar Island"],
    "Arunachal Pradesh": ["Arunanchal Pradesh"],
    "Delhi": ["NCT of Delhi"],
    "Jammu and Kashmir": ["Jammu & Kashmir"],
    "Dadra and Nagar Haveli and Daman and Diu": ["Dadara & Nagar Havelli", "Daman & Diu"],
}


def build_map_df(year):
    d = df[["State", f"Acc_{year}", f"Killed_{year}"]].copy()
    d.columns = ["State", "Accidents", "Killed"]
    # The map shows Ladakh as part of Jammu and Kashmir, so combine them
    jk_names = ["Jammu and Kashmir", "Ladakh"]
    jk = d[d["State"].isin(jk_names)][["Accidents", "Killed"]].sum()
    d = d[~d["State"].isin(jk_names)]
    d = pd.concat([d, pd.DataFrame([{"State": "Jammu and Kashmir",
                                     "Accidents": jk["Accidents"], "Killed": jk["Killed"]}])])
    rows = []
    for _, r in d.iterrows():
        for g in NAME_MAP.get(r["State"], [r["State"]]):
            rows.append({"Map name": g, "State": r["State"],
                         "Accidents": r["Accidents"], "Killed": r["Killed"]})
    m = pd.DataFrame(rows)
    m["Severity"] = (m["Killed"] / m["Accidents"] * 100).round(1)
    return m


# ---------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------
def show(fig, filename):
    """Draw a chart and add a button to download it as an interactive HTML file."""
    st.plotly_chart(fig)
    st.download_button(
        "⬇️ Download chart (interactive HTML)",
        fig.to_html(include_plotlyjs="cdn").encode("utf-8"),
        f"{filename}.html",
        "text/html",
        key=f"dl_{filename}",
    )


def fmt(x):
    return "not reported" if pd.isna(x) else f"{int(x):,}"


def pct_change(old, new):
    if pd.isna(old) or pd.isna(new) or old == 0:
        return None
    return f"{(new - old) / old * 100:.1f}% vs 2020"


def india_severity(y):
    return df[f"Killed_{y}"].sum() / df[f"Acc_{y}"].sum() * 100


def report_text(state, y):
    r = df[df["State"] == state].iloc[0]
    rank_k = df[f"Killed_{y}"].rank(ascending=False)[df["State"] == state].iloc[0]
    n_ranked = int(df[f"Killed_{y}"].notna().sum())
    sev, sev_in = r[f"Severity_{y}"], india_severity(y)
    lines = [
        f"ROAD ACCIDENT REPORT CARD: {state} ({y})",
        "Source: MoRTH, Road Accidents in India 2024",
        "",
        f"Accidents in {y}: {fmt(r[f'Acc_{y}'])}",
        f"Persons killed in {y}: {fmt(r[f'Killed_{y}'])}",
    ]
    if pd.notna(sev):
        lines.append(f"Deaths per 100 accidents: {sev:.1f} (India: {sev_in:.1f})")
    if pd.notna(rank_k):
        lines.append(f"Rank by deaths: #{int(rank_k)} of {n_ranked} states/UTs")
    lines += ["", "Year | Accidents | Killed | Deaths per 100 accidents", "--- | --- | --- | ---"]
    for yy in YEARS:
        s = r[f"Severity_{yy}"]
        lines.append(f"{yy} | {fmt(r[f'Acc_{yy}'])} | {fmt(r[f'Killed_{yy}'])} | "
                     f"{'not reported' if pd.isna(s) else f'{s:.1f}'}")
    return "\n".join(lines)


# ---------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------
st.sidebar.title("🚦 Road Safety India")
st.sidebar.caption("Explore MoRTH road accident data, 2020 to 2024")
st.sidebar.header("Filters")
year = st.sidebar.selectbox("Year", YEARS, index=len(YEARS) - 1)
top_n = st.sidebar.slider("Number of states in ranking", 5, 20, 10)
default_states = ["Uttar Pradesh", "Tamil Nadu", "Madhya Pradesh", "Kerala", "Karnataka"]
selected_states = st.sidebar.multiselect(
    "States for trend chart", sorted(df["State"]), default=default_states
)

# ---------------------------------------------------------------
# Title and summary cards
# ---------------------------------------------------------------
st.title("🚦 Road Accidents in India: State-wise Analysis")
st.caption("Source: Ministry of Road Transport and Highways (MoRTH), Road Accidents in India 2024")

acc_year = int(df[f"Acc_{year}"].sum())
killed_year = int(df[f"Killed_{year}"].sum())
acc_change = (acc_year - df["Acc_2020"].sum()) / df["Acc_2020"].sum() * 100
killed_change = (killed_year - df["Killed_2020"].sum()) / df["Killed_2020"].sum() * 100
severity_india = killed_year / acc_year * 100
up_rank = int(df[f"Killed_{year}"].rank(ascending=False)[df["State"] == "Uttar Pradesh"].iloc[0])

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"Accidents ({year})", f"{acc_year:,}", f"{acc_change:.1f}% vs 2020")
c2.metric(f"Persons killed ({year})", f"{killed_year:,}", f"{killed_change:.1f}% vs 2020")
c3.metric("Deaths per 100 accidents", f"{severity_india:.1f}")
c4.metric(f"Uttar Pradesh rank ({year}, deaths)", f"#{up_rank}")

# ---------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------
(tab_home, tab_over, tab_map, tab_trend, tab_sev,
 tab_cause, tab_card, tab_cmp, tab_data) = st.tabs([
    "🏠 Home", "Overview", "Map", "Trends", "Severity",
    "Causes", "State report card", "Compare two states", "Data and methods",
])

# ---------------- Home ----------------
with tab_home:
    st.header("About this app")
    st.write(
        "This app turns official road accident statistics into an interactive dashboard. "
        "You can see which states have the most accidents and deaths, how serious their accidents are, "
        "what causes them, and how things changed from 2020 to 2024."
    )
    st.subheader("How to use it")
    st.markdown(
        "- **Filters on the left** change the year, the length of the rankings and the states in the trend chart.\n"
        "- **Overview and Map** show where accidents and deaths are highest.\n"
        "- **Trends** shows how states changed over five years.\n"
        "- **Severity** shows where accidents are most likely to be fatal.\n"
        "- **Causes** shows which violations are linked to the most deaths.\n"
        "- **State report card** gives a one-page summary of any state, which you can download.\n"
        "- **Compare two states** puts two states side by side.\n"
        "- **Data and methods** explains the sources, the cleaning and the limitations."
    )

    st.subheader("Key findings")
    d = df.copy()
    acc_20, acc_24 = d["Acc_2020"].sum(), d["Acc_2024"].sum()
    kil_20, kil_24 = d["Killed_2020"].sum(), d["Killed_2024"].sum()
    top3 = d.sort_values("Killed_2024", ascending=False).head(3)
    top3_share = top3["Killed_2024"].sum() / kil_24 * 100
    big = d[d["Acc_2024"] >= 1000].sort_values("Severity_2024", ascending=False).iloc[0]
    up = d[d["State"] == "Uttar Pradesh"].iloc[0]
    speed = vio[vio["Violation"] == "Over-speeding"].iloc[0]
    drunk = vio[vio["Violation"].str.startswith("Drunken")].iloc[0]
    speed_share = speed["Killed_2024"] / vio["Killed_2024"].sum() * 100
    st.markdown(f"""
1. **Accidents rose {(acc_24 - acc_20) / acc_20 * 100:.1f}%** from 2020 to 2024 ({int(acc_20):,} to {int(acc_24):,}), and **deaths rose {(kil_24 - kil_20) / kil_20 * 100:.1f}%** ({int(kil_20):,} to {int(kil_24):,}). 2020 was a lockdown year, so it is an unusually low starting point.
2. **{', '.join(top3['State'])}** together account for **{top3_share:.1f}%** of all road deaths in 2024.
3. **Uttar Pradesh** recorded {int(up['Killed_2024']):,} deaths in 2024, with {up['Severity_2024']:.1f} deaths per 100 accidents, against {kil_24 / acc_24 * 100:.1f} for India.
4. Among states with at least 1,000 accidents, **{big['State']}** has the deadliest accidents: {big['Severity_2024']:.1f} deaths per 100 accidents.
5. **Over-speeding** is linked to **{speed_share:.1f}%** of deaths in 2024, while drunken driving accounts for {int(drunk['Killed_2024']):,} deaths.
""")
    st.caption(
        "These findings are calculated from the data, so they update if the data changes. "
        "Ladakh's 2020 figures are included in Jammu and Kashmir in the source."
    )

# ---------------- Overview ----------------
with tab_over:
    measure = st.radio("Show", ["Accidents", "Persons killed"], horizontal=True)
    col = f"Acc_{year}" if measure == "Accidents" else f"Killed_{year}"
    st.subheader(f"Top {top_n} states: {measure.lower()} ({year})")
    top = df[["State", col]].sort_values(col, ascending=False).head(top_n)
    fig = px.bar(top, x="State", y=col, text_auto=".3s", labels={col: measure},
                 color=col, color_continuous_scale="Reds")
    fig.update_layout(coloraxis_showscale=False)
    show(fig, "overview_top_states")

# ---------------- Map ----------------
with tab_map:
    st.subheader(f"Map of India ({year})")
    what = st.radio("Colour states by", ["Accidents", "Killed", "Severity"],
                    horizontal=True, key="mapmeasure")
    m = build_map_df(year)
    fig = px.choropleth(
        m, geojson=geo, locations="Map name", featureidkey="properties.ST_NM",
        color=what, hover_name="State",
        hover_data={"Map name": False, "Accidents": ":,", "Killed": ":,", "Severity": True},
        color_continuous_scale="Reds",
        labels={"Severity": "Deaths per 100 accidents"},
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=650)
    show(fig, "india_map")
    st.caption(
        "Ladakh is shown together with Jammu and Kashmir, and Dadra and Nagar Haveli and Daman and Diu "
        "share one value. Boundaries come from open community data (DataMeet) and are indicative only."
    )

# ---------------- Trends ----------------
with tab_trend:
    measure2 = st.radio("Show trend of", ["Accidents", "Killed"], horizontal=True)
    st.subheader(f"{measure2} over time, 2020 to 2024")
    if selected_states:
        sub = long_df[long_df["State"].isin(selected_states)]
        fig = px.line(sub, x="Year", y=measure2, color="State", markers=True)
        fig.update_xaxes(tickvals=YEARS)
        show(fig, "trend_states")
    else:
        st.warning("Pick at least one state in the sidebar.")
    nat = long_df.groupby("Year", as_index=False)[["Accidents", "Killed"]].sum()
    st.subheader("India total")
    fig2 = px.line(nat, x="Year", y=measure2, markers=True)
    fig2.update_xaxes(tickvals=YEARS)
    show(fig2, "trend_india")

# ---------------- Severity ----------------
with tab_sev:
    st.subheader(f"Severity: deaths per 100 accidents ({year})")
    st.caption(
        "A high value means accidents in that state are more likely to be fatal. "
        "States with very few accidents can show extreme values, so you can hide them below."
    )
    min_acc = st.slider("Ignore states with fewer accidents than", 0, 5000, 1000, step=250)
    sev = df[df[f"Acc_{year}"] >= min_acc][["State", f"Acc_{year}", f"Killed_{year}", f"Severity_{year}"]]
    sev = sev.sort_values(f"Severity_{year}", ascending=False).head(top_n)
    fig = px.bar(sev, x="State", y=f"Severity_{year}", text_auto=".1f",
                 labels={f"Severity_{year}": "Deaths per 100 accidents"},
                 color=f"Severity_{year}", color_continuous_scale="Reds")
    fig.update_layout(coloraxis_showscale=False)
    show(fig, "severity_top_states")
    st.write(f"India overall: **{severity_india:.1f}** deaths per 100 accidents in {year}.")

    st.subheader("Accidents vs deaths")
    fig3 = px.scatter(df, x=f"Acc_{year}", y=f"Killed_{year}", hover_name="State",
                      labels={f"Acc_{year}": "Accidents", f"Killed_{year}": "Persons killed"})
    show(fig3, "accidents_vs_deaths")

# ---------------- Causes ----------------
with tab_cause:
    st.subheader("What causes accidents? (type of violation, 2024)")
    st.caption("Source: MoRTH, Road Accidents in India 2024. 'Others' covers all other causes.")
    measure4 = st.radio("Show", ["Accidents", "Killed", "Injured"], horizontal=True, key="vio")
    vcol = {"Accidents": "Acc_2024", "Killed": "Killed_2024", "Injured": "Injured_2024"}[measure4]
    fig = px.bar(vio.sort_values(vcol, ascending=False), x="Violation", y=vcol, text_auto=".3s",
                 labels={vcol: measure4}, color=vcol, color_continuous_scale="Reds")
    fig.update_layout(coloraxis_showscale=False)
    show(fig, "causes_by_violation")
    table_v = vio[["Violation", "Acc_2024", "Killed_2024", "Injured_2024", "Deaths_per_100_Acc_2024"]].copy()
    table_v.columns = ["Violation", "Accidents", "Killed", "Injured", "Deaths per 100 accidents"]
    st.dataframe(table_v, use_container_width=True)
    st.download_button(
        "⬇️ Download violations table (CSV)",
        table_v.to_csv(index=False).encode("utf-8"),
        "violations_summary_2024.csv", "text/csv", key="dl_vio_summary",
    )

# ---------------- State report card ----------------
with tab_card:
    st.subheader("State report card")
    names_card = sorted(df["State"])
    card_state = st.selectbox("Choose a state or UT", names_card,
                              index=names_card.index("Uttar Pradesh"), key="card_state")
    st.caption(f"Showing {year}. Change the year in the sidebar.")
    r = df[df["State"] == card_state].iloc[0]
    acc_v, kil_v, sev_v = r[f"Acc_{year}"], r[f"Killed_{year}"], r[f"Severity_{year}"]
    sev_in = india_severity(year)
    rank_series = df[f"Killed_{year}"].rank(ascending=False)
    rank_v = rank_series[df["State"] == card_state].iloc[0]
    n_ranked = int(df[f"Killed_{year}"].notna().sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"Accidents ({year})", fmt(acc_v), pct_change(r["Acc_2020"], acc_v) if year != 2020 else None)
    k2.metric(f"Persons killed ({year})", fmt(kil_v), pct_change(r["Killed_2020"], kil_v) if year != 2020 else None)
    k3.metric("Deaths per 100 accidents",
              "not reported" if pd.isna(sev_v) else f"{sev_v:.1f}",
              None if pd.isna(sev_v) else f"{sev_v - sev_in:+.1f} vs India", delta_color="inverse")
    k4.metric("Rank by deaths", "n/a" if pd.isna(rank_v) else f"#{int(rank_v)} of {n_ranked}")

    if pd.notna(sev_v):
        word = "higher" if sev_v > sev_in else "lower"
        st.info(
            f"In {year}, {card_state} recorded {fmt(acc_v)} accidents and {fmt(kil_v)} deaths. "
            f"Its severity of {sev_v:.1f} deaths per 100 accidents is {word} than the India average of {sev_in:.1f}."
        )
    else:
        st.info(f"Figures for {card_state} are not reported for {year}.")

    state_rows = long_df[long_df["State"] == card_state]
    left, right = st.columns(2)
    with left:
        f1 = px.bar(state_rows, x="Year", y="Accidents", title="Accidents per year",
                    color_discrete_sequence=["#d62728"])
        f1.update_xaxes(tickvals=YEARS)
        show(f1, "card_accidents")
    with right:
        f2 = px.bar(state_rows, x="Year", y="Killed", title="Persons killed per year",
                    color_discrete_sequence=["#7f0000"])
        f2.update_xaxes(tickvals=YEARS)
        show(f2, "card_killed")

    sev_trend = pd.DataFrame({
        "Year": YEARS * 2,
        "Deaths per 100 accidents": [r[f"Severity_{y}"] for y in YEARS] + [india_severity(y) for y in YEARS],
        "Series": [card_state] * len(YEARS) + ["India"] * len(YEARS),
    })
    f3 = px.line(sev_trend, x="Year", y="Deaths per 100 accidents", color="Series", markers=True,
                 title=f"Severity: {card_state} vs India")
    f3.update_xaxes(tickvals=YEARS)
    show(f3, "card_severity")

    safe_name = card_state.lower().replace(" ", "_")
    st.download_button(
        "⬇️ Download this report card (text file)",
        report_text(card_state, year).encode("utf-8"),
        f"report_card_{safe_name}_{year}.txt", "text/plain", key="dl_report",
    )

# ---------------- Compare ----------------
with tab_cmp:
    st.subheader("Compare two states")
    names = sorted(df["State"])
    col_a, col_b = st.columns(2)
    state_a = col_a.selectbox("State A", names, index=names.index("Uttar Pradesh"))
    state_b = col_b.selectbox("State B", names, index=names.index("Tamil Nadu"))
    pair = long_df[long_df["State"].isin([state_a, state_b])]
    left, right = st.columns(2)
    with left:
        f1 = px.line(pair, x="Year", y="Accidents", color="State", markers=True, title="Accidents")
        f1.update_xaxes(tickvals=YEARS)
        show(f1, "compare_accidents")
    with right:
        f2 = px.line(pair, x="Year", y="Killed", color="State", markers=True, title="Persons killed")
        f2.update_xaxes(tickvals=YEARS)
        show(f2, "compare_killed")
    table = df[df["State"].isin([state_a, state_b])].set_index("State")[
        [f"Acc_{year}", f"Killed_{year}", f"Severity_{year}"]
    ]
    table.columns = [f"Accidents ({year})", f"Killed ({year})", f"Deaths per 100 accidents ({year})"]
    st.dataframe(table, use_container_width=True)
    st.download_button(
        "⬇️ Download state comparison table (CSV)",
        table.to_csv().encode("utf-8"),
        f"state_comparison_{year}.csv", "text/csv", key="dl_compare_table",
    )

# ---------------- Data and methods ----------------
with tab_data:
    st.header("Data and methods")

    with st.expander("Data sources", expanded=True):
        st.markdown(
            "- **Accident, death and injury figures:** Ministry of Road Transport and Highways (MoRTH), "
            "*Road Accidents in India 2024*, as published in table form on the OpenCity data portal.\n"
            "- **Map boundaries:** DataMeet, an open community project. Boundaries are indicative only.\n"
            "- **Period covered:** 2020 to 2024 for states, and 2023 to 2024 for causes (type of violation)."
        )

    with st.expander("How the data was cleaned"):
        st.markdown(
            "- Numbers written in Indian style (for example 1,38,383) were converted to real numbers.\n"
            "- The 'All India' row and footnote lines were removed from the state tables. "
            "The All India totals were used to check that the 36 states add up exactly.\n"
            "- State names were made consistent between the accidents and deaths tables "
            "(for example 'J & K #' became 'Jammu and Kashmir', and '&' became 'and').\n"
            "- Ladakh has no 2020 figures because the source includes them in Jammu and Kashmir. "
            "These cells were left blank, not filled with guesses.\n"
            "- Percentage-share rows in the causes table were removed, because the app calculates shares itself."
        )

    with st.expander("How the measures are calculated"):
        st.markdown(
            "- **Severity (deaths per 100 accidents)** = persons killed ÷ accidents × 100.\n"
            "- **Change vs 2020** = (value in selected year − value in 2020) ÷ value in 2020 × 100.\n"
            "- **Rank by deaths** = position among the states and UTs that reported a figure for that year."
        )

    with st.expander("Limitations"):
        st.markdown(
            "- The data is yearly state-level totals. It has no accident locations, times or driver details.\n"
            "- Severity depends on how completely each state records minor accidents, "
            "so a high value does not by itself mean a state's roads are more dangerous.\n"
            "- States with few accidents can show extreme severity values.\n"
            "- 2020 was a COVID-19 lockdown year, so comparisons with 2020 overstate growth.\n"
            "- Causes data covers 2023 and 2024 only, and 'Others' is a large category."
        )

    st.subheader("States data")
    st.dataframe(df, use_container_width=True)
    st.download_button("⬇️ Download states data (CSV)", df.to_csv(index=False).encode("utf-8"),
                       "states_data.csv", "text/csv", key="dl_states")
    st.subheader("Causes data")
    st.dataframe(vio, use_container_width=True)
    st.download_button("⬇️ Download causes data (CSV)", vio.to_csv(index=False).encode("utf-8"),
                       "causes_data.csv", "text/csv", key="dl_vio")

st.divider()
st.caption("🚦 Road Safety India | Built with Python, pandas, Plotly and Streamlit | Data: MoRTH, Road Accidents in India 2024.")

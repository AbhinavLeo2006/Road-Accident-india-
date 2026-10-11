import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Road Accidents in India", page_icon="🚦", layout="wide")

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


df = load(STATES_CSV)
vio = load(VIOLATIONS_CSV)


@st.cache_data
def load_geo():
    with open(folder / GEOJSON, encoding="utf-8") as f:
        return json.load(f)


geo = load_geo()

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

# One row per state per year, for line charts
long_df = pd.concat(
    [
        df.melt(id_vars="State", value_vars=[f"Acc_{y}" for y in YEARS],
                var_name="Year", value_name="Accidents")
        .assign(Year=lambda d: d["Year"].str[-4:].astype(int)),
    ]
).merge(
    df.melt(id_vars="State", value_vars=[f"Killed_{y}" for y in YEARS],
            var_name="Year", value_name="Killed")
    .assign(Year=lambda d: d["Year"].str[-4:].astype(int)),
    on=["State", "Year"],
)

# ---------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------
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
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
    ["Overview", "Map", "Trends", "Severity", "Causes", "Compare two states", "Insights", "Data"]
)

with tab1:
    measure = st.radio("Show", ["Accidents", "Persons killed"], horizontal=True)
    col = f"Acc_{year}" if measure == "Accidents" else f"Killed_{year}"
    st.subheader(f"Top {top_n} states: {measure.lower()} ({year})")
    top = df[["State", col]].sort_values(col, ascending=False).head(top_n)
    fig = px.bar(top, x="State", y=col, text_auto=".3s", labels={col: measure},
                 color=col, color_continuous_scale="Reds")
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig)

with tab2:
    st.subheader(f"Map of India ({year})")
    what = st.radio("Colour states by", ["Accidents", "Killed", "Severity"], horizontal=True, key="mapmeasure")
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
    st.plotly_chart(fig)
    st.caption(
        "Ladakh is shown together with Jammu and Kashmir, and Dadra and Nagar Haveli and Daman and Diu "
        "share one value. Boundaries come from open community data (DataMeet) and are indicative only."
    )

with tab3:
    measure2 = st.radio("Show trend of", ["Accidents", "Killed"], horizontal=True)
    st.subheader(f"{measure2} over time, 2020 to 2024")
    if selected_states:
        sub = long_df[long_df["State"].isin(selected_states)]
        fig = px.line(sub, x="Year", y=measure2, color="State", markers=True)
        fig.update_xaxes(tickvals=YEARS)
        st.plotly_chart(fig)
    else:
        st.warning("Pick at least one state in the sidebar.")
    nat = long_df.groupby("Year", as_index=False)[["Accidents", "Killed"]].sum()
    st.subheader("India total")
    fig2 = px.line(nat, x="Year", y=measure2, markers=True)
    fig2.update_xaxes(tickvals=YEARS)
    st.plotly_chart(fig2)

with tab4:
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
    st.plotly_chart(fig)
    st.write(f"India overall: **{severity_india:.1f}** deaths per 100 accidents in {year}.")

    st.subheader("Accidents vs deaths")
    fig3 = px.scatter(df, x=f"Acc_{year}", y=f"Killed_{year}", hover_name="State",
                      labels={f"Acc_{year}": "Accidents", f"Killed_{year}": "Persons killed"})
    st.plotly_chart(fig3)

with tab5:
    st.subheader("What causes accidents? (type of violation, 2024)")
    st.caption("Source: MoRTH, Road Accidents in India 2024. 'Others' covers all other causes.")
    measure4 = st.radio("Show", ["Accidents", "Killed", "Injured"], horizontal=True, key="vio")
    vcol = {"Accidents": "Acc_2024", "Killed": "Killed_2024", "Injured": "Injured_2024"}[measure4]
    fig = px.bar(vio.sort_values(vcol, ascending=False), x="Violation", y=vcol, text_auto=".3s",
                 labels={vcol: measure4}, color=vcol, color_continuous_scale="Reds")
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig)
    show = vio[["Violation", "Acc_2024", "Killed_2024", "Injured_2024", "Deaths_per_100_Acc_2024"]].copy()
    show.columns = ["Violation", "Accidents", "Killed", "Injured", "Deaths per 100 accidents"]
    st.dataframe(show)

with tab6:
    st.subheader("Compare two states")
    names = sorted(df["State"])
    col_a, col_b = st.columns(2)
    state_a = col_a.selectbox("State A", names, index=names.index("Uttar Pradesh"))
    state_b = col_b.selectbox("State B", names, index=names.index("Tamil Nadu"))
    pair = long_df[long_df["State"].isin([state_a, state_b])]
    left, right = st.columns(2)
    f1 = px.line(pair, x="Year", y="Accidents", color="State", markers=True, title="Accidents")
    f1.update_xaxes(tickvals=YEARS)
    left.plotly_chart(f1)
    f2 = px.line(pair, x="Year", y="Killed", color="State", markers=True, title="Persons killed")
    f2.update_xaxes(tickvals=YEARS)
    right.plotly_chart(f2)
    table = df[df["State"].isin([state_a, state_b])].set_index("State")[
        [f"Acc_{year}", f"Killed_{year}", f"Severity_{year}"]
    ]
    table.columns = [f"Accidents ({year})", f"Killed ({year})", f"Deaths per 100 accidents ({year})"]
    st.table(table)

with tab7:
    st.subheader("Key insights (calculated from the data)")
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
5. **Over-speeding** is linked to **{speed_share:.1f}%** of deaths in 2024, while drunken driving accounts for only {int(drunk['Killed_2024']):,} deaths.
""")
    st.caption(
        "Notes: Ladakh's 2020 figures are included in Jammu and Kashmir in the source. "
        "Deaths per 100 accidents depends on how well each state records minor accidents."
    )

with tab8:
    st.subheader("States data")
    st.dataframe(df)
    st.download_button("Download states data", df.to_csv(index=False).encode("utf-8"),
                       STATES_CSV, "text/csv")
    st.subheader("Violation data")
    st.dataframe(vio)
    st.download_button("Download violation data", vio.to_csv(index=False).encode("utf-8"),
                       VIOLATIONS_CSV, "text/csv")

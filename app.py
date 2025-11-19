import requests
import pandas as pd
import streamlit as st
import altair as alt

@st.cache_data(show_spinner="Loading data...")
def fetch_fpl_data():
    url = 'https://fantasy.premierleague.com/api/bootstrap-static/'
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

# Fetch data
data = fetch_fpl_data()

# Players & Teams DataFrames
players_df = pd.DataFrame(data['elements'])
teams_df = pd.DataFrame(data['teams'])

# Prepare teams for merge (get id, name, code)
teams_df = teams_df.rename(
    columns={"id": "team_id", "code": "team_code", "name": "team_name"}
)[["team_id", "team_name", "team_code"]]

# Merge: add team_name and team_code to players
players = players_df.merge(
    teams_df,
    left_on="team",
    right_on="team_id",
    how="left"
)

# Add logo_url column
players["team_code"] = players["team_code"].astype(str).str.zfill(3)
players["logo_url"] = (
    "https://resources.premierleague.com/premierleague/badges/70/t"
    + players["team_code"]
    + ".png"
)

# Add Points Per Million column
players["Points Per Million"] = players["total_points"] / players["now_cost"]

# Compose a player name for tooltips
players['Name'] = players['first_name'] + " " + players['second_name']
players['Cost'] = players['now_cost'] / 10

# Get position names
position_map = {row["id"]: row["singular_name"] for row in data["element_types"]}
players["element_type"] = players["element_type"].map(position_map)

# Streamlit App
st.set_page_config(page_title="FPL Moneyball Dashboard", layout="wide")
st.title("FPL Moneyball Dashboard")

# Scatter plot (Cost vs Points) by Position
scatter = alt.Chart(players).mark_circle(size=90).encode(
    x=alt.X("Cost:Q", title="Price (£m)"),
    y=alt.Y("total_points:Q", title="Total Points"),
    color=alt.Color("element_type:N", title="Position"),
    tooltip=[
        alt.Tooltip("Name:N", title="Player"),
        alt.Tooltip("team_name:N", title="Team"),
        alt.Tooltip("total_points:Q", title="Points"),
        alt.Tooltip("Cost:Q", title="Cost (£m)")
    ],
).interactive().properties(
    width=780,
    height=480,
    title="Player Cost vs Total Points (by Position)"
)
st.altair_chart(scatter, use_container_width=True)

# Show top 50 by Points Per Million
st.subheader("Top 50 Players by Points Per Million (£m)")
top_ppm = players.sort_values("Points Per Million", ascending=False).head(50).copy()

to_show = top_ppm[[
    "Name", "element_type", "team_name", "Cost",
    "total_points", "Points Per Million", "logo_url"
]].rename(
    columns={
        "element_type": "Position",
        "team_name": "Team",
        "total_points": "Points"
    }
)

st.dataframe(
    to_show,
    use_container_width=True,
    column_config={
        "logo_url": st.column_config.ImageColumn("Badge", help="Club Badge"),
        "Points Per Million": st.column_config.NumberColumn(format="%.2f"),
        "Cost": st.column_config.NumberColumn(format="%.1f"),
    }
)

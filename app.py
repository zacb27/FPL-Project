import streamlit as st
import pandas as pd
import requests
import re

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(page_title="FPL Vibe Scout", layout="wide")
st.title("⚽ FPL Vibe Scout")
st.markdown("### The 'Moneyball' Dashboard for Fantasy Premier League")

# --- 2. DATA LOADING FUNCTION (Cached for Speed) ---
@st.cache_data
def load_data():
    url = 'https://fantasy.premierleague.com/api/bootstrap-static/'
    r = requests.get(url)
    json_data = r.json()
    
    # Create DataFrames
    elements_df = pd.DataFrame(json_data['elements'])
    teams_df = pd.DataFrame(json_data['teams'])
    
    # Map Team Names (The ID in elements matches ID in teams)
    team_id_to_name = teams_df.set_index('id')['name'].to_dict()
    team_id_to_short = teams_df.set_index('id')['short_name'].to_dict()
    elements_df['team_name'] = elements_df['team'].map(team_id_to_name)
    
    # Calculate Metrics
    elements_df['cost'] = elements_df['now_cost'] / 10
    elements_df['ppm'] = elements_df['total_points'] / elements_df['cost']
    elements_df['ppm'] = elements_df['ppm'].fillna(0)  # Handle zeros
    
    # Create player photo URLs
    photo_ids = elements_df['photo'].str.replace(".jpg", "", regex=False)
    photo_ids = photo_ids.apply(lambda x: x if x.startswith("p") else f"p{x}")
    elements_df['photo_url'] = (
        "https://resources.premierleague.com/premierleague/photos/players/110x140/"
        + photo_ids
        + ".png"
    )
    
    # Fetch fixtures data for upcoming matches
    fixtures_url = 'https://fantasy.premierleague.com/api/fixtures/'
    fixtures_response = requests.get(fixtures_url)
    fixtures_data = fixtures_response.json()
    fixtures_df = pd.DataFrame(fixtures_data)

    next_fixture_map = {}
    if not fixtures_df.empty:
        upcoming_fixtures = fixtures_df[fixtures_df['finished'] == False].copy()
        if not upcoming_fixtures.empty:
            upcoming_fixtures['kickoff_time'] = pd.to_datetime(upcoming_fixtures['kickoff_time'])
            upcoming_fixtures = upcoming_fixtures.sort_values('kickoff_time')
            for team_id in team_id_to_short.keys():
                team_fixtures = upcoming_fixtures[
                    (upcoming_fixtures['team_h'] == team_id) | (upcoming_fixtures['team_a'] == team_id)
                ].head(3)
                fixtures_list = []
                for _, fixture in team_fixtures.iterrows():
                    if fixture['team_h'] == team_id:
                        opponent = team_id_to_short.get(fixture['team_a'], 'UNK')
                        fixtures_list.append(f"vs {opponent} (H)")
                    else:
                        opponent = team_id_to_short.get(fixture['team_h'], 'UNK')
                        fixtures_list.append(f"@ {opponent} (A)")
                next_fixture_map[team_id] = ", ".join(fixtures_list) if fixtures_list else "No fixtures scheduled"
    elements_df['next_3_fixtures'] = elements_df['team'].map(next_fixture_map).fillna("No fixtures scheduled")

    return elements_df

# Helper: Smart search parser
def apply_smart_search(query_text, data):
    if not query_text:
        return data, []
    filters_applied = []
    filtered = data.copy()
    q_lower = query_text.lower()
    pos_labels = {'GKP': 'Goalkeepers', 'DEF': 'Defenders', 'MID': 'Midfielders', 'FWD': 'Forwards'}

    # Position filter
    pos_keywords = {'gkp': 'GKP', 'mid': 'MID', 'def': 'DEF', 'fwd': 'FWD', 'fw': 'FWD'}
    for key, pos_code in pos_keywords.items():
        if key in q_lower:
            filtered = filtered[filtered['position'] == pos_code]
            filters_applied.append(pos_labels.get(pos_code, pos_code))
            break

    # Cost filter
    cost_match = re.search(r"(?:under|<)\s*£?\s*(\d+(\.\d+)?)", q_lower)
    if cost_match:
        cost_limit = float(cost_match.group(1))
        filtered = filtered[filtered['cost'] <= cost_limit]
        filters_applied.append(f"under £{cost_limit:.1f}m")

    # Sorting
    if "value" in q_lower:
        filtered = filtered.sort_values('ppm', ascending=False)
        filters_applied.append("sorted by value")
    elif "best" in q_lower or "top" in q_lower:
        filtered = filtered.sort_values('total_points', ascending=False)
        filters_applied.append("sorted by points")

    return filtered, filters_applied


def format_filter_message(filters):
    if not filters:
        return ""
    if len(filters) == 1:
        return filters[0]
    if len(filters) == 2:
        return " and ".join(filters)
    return ", ".join(filters[:-1]) + ", and " + filters[-1]

# Load the data
df = load_data()

# --- 3. SMART SEARCH + SIDEBAR FILTERS ---
query = st.text_input("💡 Ask the Scout (e.g., 'Best MID under 6.0')", "")

st.sidebar.header("🎯 Scout Filters")
min_minutes = st.sidebar.slider("Min Minutes Played", 0, 3000, 500)
max_price = st.sidebar.slider("Max Price (£)", 4.0, 15.0, 15.0)
positions = st.sidebar.multiselect(
    "Positions", 
    ['GKP', 'DEF', 'MID', 'FWD'], 
    default=['MID', 'FWD']
)

# Map API position IDs (1=GKP, 2=DEF, 3=MID, 4=FWD)
pos_map = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}
df['position'] = df['element_type'].map(pos_map)

# Apply Filters
filtered_df = df[
    (df['minutes'] >= min_minutes) &
    (df['cost'] <= max_price) &
    (df['position'].isin(positions))
]

display_df = filtered_df
if query.strip():
    display_df, applied = apply_smart_search(query, df)
    if applied:
        st.success("Showing " + format_filter_message(applied))
    else:
        st.info("No matching filters detected. Showing all players.")

# --- 4. THE VISUALS ---

# Tab Layout
tab1, tab2 = st.tabs(["📊 Moneyball Chart", "🏆 Dream Team Builder"])

with tab1:
    st.subheader("Value vs. Performance")
    
    # Simple Scatter Plot
    st.scatter_chart(
        display_df,
        x='cost',
        y='total_points',
        color='position',
        size='ppm',
        use_container_width=True
    )
    
    # The Data Table with Images
    st.subheader("Top Value Picks")
    display_cols = ['photo_url', 'web_name', 'team_name', 'position', 'cost', 'total_points', 'ppm', 'next_3_fixtures']
    
    st.dataframe(
        display_df[display_cols].sort_values('ppm', ascending=False).head(50),
        column_config={
            "photo_url": st.column_config.ImageColumn("Player", width="small"),
            "ppm": st.column_config.NumberColumn("Points per Million", format="%.2f"),
            "cost": st.column_config.NumberColumn("Price", format="£%.1f"),
            "next_3_fixtures": st.column_config.TextColumn("Next 3 Fixtures"),
        },
        use_container_width=True,
        hide_index=True
    )

with tab2:
    st.subheader("🤖 Auto-Pick Dream Team")
    
    budget = st.slider("Team Budget (£m)", 80.0, 105.0, 100.0)
    formation = st.selectbox("Formation", ["3-4-3", "3-5-2", "4-4-2", "4-3-3"])
    
    if st.button("Generate Team"):
        # Parse formation
        defs, mids, fwds = map(int, formation.split("-"))
        gkps = 1
        
        # Simple Greedy Algorithm
        dream_team = []
        current_cost = 0
        
        # Helper function to pick best players
        def pick_best(pos_name, count, current_team):
            available = df[df['position'] == pos_name].sort_values('total_points', ascending=False)
            picked = []
            for _, player in available.iterrows():
                if len(picked) < count:
                    picked.append(player)
            return picked

        # Pick the squad
        squad = []
        squad += pick_best('GKP', gkps, squad)
        squad += pick_best('DEF', defs, squad)
        squad += pick_best('MID', mids, squad)
        squad += pick_best('FWD', fwds, squad)
        
        squad_df = pd.DataFrame(squad)
        
        # Display
        total_points = squad_df['total_points'].sum()
        total_cost = squad_df['cost'].sum()
        
        col1, col2 = st.columns(2)
        col1.metric("Projected Points", int(total_points))
        col2.metric("Total Cost", f"£{total_cost:.1f}m", delta=f"{budget - total_cost:.1f}m left")
        
        st.dataframe(
            squad_df[['web_name', 'position', 'team_name', 'total_points', 'cost']],
            use_container_width=True
        )
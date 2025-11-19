import streamlit as st
import pandas as pd
import requests

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
    elements_df['team_name'] = elements_df['team'].map(team_id_to_name)
    
    # Calculate Metrics
    elements_df['cost'] = elements_df['now_cost'] / 10
    elements_df['ppm'] = elements_df['total_points'] / elements_df['cost']
    elements_df['ppm'] = elements_df['ppm'].fillna(0)  # Handle zeros
    
    # Create Logo URLs (Crucial Step!)
    # We use the 'team_code' column which is standard in the API
    elements_df['team_code_str'] = elements_df['team_code'].astype(str).str.zfill(3)
    elements_df['logo_url'] = (
        "https://resources.premierleague.com/premierleague/badges/70/t" 
        + elements_df['team_code_str'] 
        + ".png"
    )
    
    return elements_df

# Load the data
df = load_data()

# --- 3. SIDEBAR FILTERS ---
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

# --- 4. THE VISUALS ---

# Tab Layout
tab1, tab2 = st.tabs(["📊 Moneyball Chart", "🏆 Dream Team Builder"])

with tab1:
    st.subheader("Value vs. Performance")
    
    # Simple Scatter Plot
    st.scatter_chart(
        filtered_df,
        x='cost',
        y='total_points',
        color='position',
        size='ppm',
        use_container_width=True
    )
    
    # The Data Table with Images
    st.subheader("Top Value Picks")
    display_cols = ['logo_url', 'web_name', 'team_name', 'position', 'cost', 'total_points', 'ppm']
    
    st.dataframe(
        filtered_df[display_cols].sort_values('ppm', ascending=False).head(50),
        column_config={
            "logo_url": st.column_config.ImageColumn("Club", width="small"),
            "ppm": st.column_config.NumberColumn("Points per Million", format="%.2f"),
            "cost": st.column_config.NumberColumn("Price", format="£%.1f"),
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
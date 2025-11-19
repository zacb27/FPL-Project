import streamlit as st
import pandas as pd
import requests
import re
import altair as alt
import plotly.express as px

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
    events_df = pd.DataFrame(json_data['events'])
    
    # Map Team Names (The ID in elements matches ID in teams)
    team_id_to_name = teams_df.set_index('id')['name'].to_dict()
    team_id_to_short = teams_df.set_index('id')['short_name'].to_dict()
    strength_home = teams_df.set_index('id')['strength_overall_home'].to_dict()
    strength_away = teams_df.set_index('id')['strength_overall_away'].to_dict()
    strength_values = list(strength_home.values()) + list(strength_away.values())
    min_strength = min(strength_values) if strength_values else 0
    max_strength = max(strength_values) if strength_values else 1
    elements_df['team_name'] = elements_df['team'].map(team_id_to_name)
    elements_df['team_short'] = elements_df['team'].map(team_id_to_short)
    
    # Calculate Metrics
    elements_df['cost'] = elements_df['now_cost'] / 10
    elements_df['ppm'] = elements_df['total_points'] / elements_df['cost']
    elements_df['ppm'] = elements_df['ppm'].fillna(0)  # Handle zeros
    elements_df['points_per_game'] = pd.to_numeric(elements_df['points_per_game'], errors='coerce').fillna(0)
    
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
    fixture_ease_map = {}
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
                difficulty_values = []
                for _, fixture in team_fixtures.iterrows():
                    if fixture['team_h'] == team_id:
                        opponent = team_id_to_short.get(fixture['team_a'], 'UNK')
                        opponent_strength = strength_away.get(fixture['team_a'], (min_strength + max_strength) / 2)
                        fixtures_list.append(f"vs {opponent} (H)")
                        difficulty_values.append(opponent_strength)
                    else:
                        opponent = team_id_to_short.get(fixture['team_h'], 'UNK')
                        opponent_strength = strength_home.get(fixture['team_h'], (min_strength + max_strength) / 2)
                        fixtures_list.append(f"@ {opponent} (A)")
                        difficulty_values.append(opponent_strength)
                next_fixture_map[team_id] = ", ".join(fixtures_list) if fixtures_list else "No fixtures scheduled"
                if difficulty_values:
                    avg_strength = sum(difficulty_values) / len(difficulty_values)
                    strength_range = max_strength - min_strength if max_strength != min_strength else 1
                    normalized_ease = 1 - ((avg_strength - min_strength) / strength_range)
                    fixture_ease_map[team_id] = max(0, min(1, normalized_ease))
                else:
                    fixture_ease_map[team_id] = 0.5
    elements_df['next_3_fixtures'] = elements_df['team'].map(next_fixture_map).fillna("No fixtures scheduled")
    elements_df['fixture_ease_score'] = elements_df['team'].map(fixture_ease_map).fillna(0.5)
    elements_df['fixture_difficulty_rating'] = elements_df['points_per_game'] * (1 + elements_df['fixture_ease_score'])

    return elements_df, events_df


@st.cache_data
def fetch_player_history(player_id):
    url = f"https://fantasy.premierleague.com/api/element-summary/{player_id}/"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


@st.cache_data
def fetch_event_live(event_id):
    url = f"https://fantasy.premierleague.com/api/event/{event_id}/live/"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()

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


def build_team_of_week(event_id, master_df):
    try:
        live_data = fetch_event_live(event_id)
    except requests.RequestException:
        return pd.DataFrame()

    live_elements = pd.json_normalize(live_data.get('elements', []))
    if live_elements.empty or 'stats.total_points' not in live_elements:
        return pd.DataFrame()

    live_stats = live_elements[['id', 'stats.total_points']].rename(columns={'stats.total_points': 'gw_points'})
    merged = master_df.merge(live_stats, left_on='id', right_on='id', how='inner')

    lineup_parts = []
    requirements = {'GKP': 1, 'DEF': 4, 'MID': 4, 'FWD': 3}

    for pos, count in requirements.items():
        pos_players = merged[merged['position'] == pos].sort_values('gw_points', ascending=False)
        if pos_players.empty:
            continue
        lineup_parts.append(pos_players.head(count))

    if not lineup_parts:
        return pd.DataFrame()

    lineup_df = pd.concat(lineup_parts, ignore_index=True)
    lineup_df = lineup_df[['web_name', 'team_name', 'team_short', 'position', 'gw_points', 'photo_url']]
    return lineup_df


def render_lineup(lineup_df, gameweek):
    st.caption(f"Best XI from Gameweek {gameweek}")

    def row_display(players_subset):
        if players_subset.empty:
            return
        cols = st.columns(len(players_subset))
        for col, (_, player) in zip(cols, players_subset.iterrows()):
            card_html = f"""
            <div style="
                background: linear-gradient(145deg, #1a1a1a, #2d0c3d);
                border-radius: 18px;
                padding: 16px;
                text-align: center;
                color: #ffffff;
                font-family: 'Inter', sans-serif;
                box-shadow: 0 10px 25px rgba(0,0,0,0.35);
            ">
                <div style="font-size: 0.85rem; color: #b8b8ff; margin-bottom: 8px;">{player['team_short']}</div>
                <div style="
                    margin: 0 auto 12px;
                    width: 70px;
                    height: 90px;
                    border-radius: 50% 50% 45% 45%;
                    background: linear-gradient(180deg, #5b21b6 0%, #7c3aed 100%);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: 600;
                    letter-spacing: 0.05em;
                    color: #fff;
                    border: 2px solid rgba(255,255,255,0.15);
                ">{player['web_name']}</div>
                <div style="font-size: 0.9rem; color: #ddd;">{player['position']}</div>
                <div style="font-size: 1.2rem; font-weight: 700; color: #ffd166;">{player['gw_points']} pts</div>
            </div>
            """
            col.markdown(card_html, unsafe_allow_html=True)

    formation_rows = [
        lineup_df[lineup_df['position'] == 'GKP'],
        lineup_df[lineup_df['position'] == 'DEF'],
        lineup_df[lineup_df['position'] == 'MID'],
        lineup_df[lineup_df['position'] == 'FWD'],
    ]

    for row in formation_rows:
        row_display(row)

# Load the data
df, events_df = load_data()

# --- 3. NAVIGATION MENU ---
page = st.sidebar.radio(
    "📍 Navigation",
    ["Home Dashboard", "Player Compare", "League Spy", "Form Tracker"]
)

# Map API position IDs (1=GKP, 2=DEF, 3=MID, 4=FWD)
pos_map = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}
df['position'] = df['element_type'].map(pos_map)

if page == "Home Dashboard":
    # Smart search input
    query = st.text_input("💡 Ask the Scout (e.g., 'Best MID under 6.0')", "")

    # Sidebar filters
    st.sidebar.header("🎯 Scout Filters")
    min_minutes = st.sidebar.slider("Min Minutes Played", 0, 3000, 500)
    max_price = st.sidebar.slider("Max Price (£)", 4.0, 15.0, 15.0)
    positions = st.sidebar.multiselect(
        "Positions",
        ['GKP', 'DEF', 'MID', 'FWD'],
        default=['MID', 'FWD']
    )

    # Apply filters
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

    # Tabs for dashboard
    tab1, tab2 = st.tabs(["📊 Moneyball Chart", "🏆 Dream Team Builder"])

    with tab1:
        st.subheader("Value vs. Performance")

        # Interactive scatter plot
        if not display_df.empty:
            scatter_data = display_df.copy()
            chart = (
                alt.Chart(scatter_data)
                .mark_circle(opacity=0.8)
                .encode(
                    x=alt.X('cost', title='Price (£m)', scale=alt.Scale(domain=[3.5, 15])),
                    y=alt.Y('total_points', title='Total Points'),
                    color=alt.Color('position', title='Position'),
                    size=alt.Size('ppm', title='Points per Million', scale=alt.Scale(range=[50, 500])),
                    tooltip=[
                        alt.Tooltip('web_name', title='Player'),
                        alt.Tooltip('team_name', title='Team'),
                        alt.Tooltip('position', title='Position'),
                        alt.Tooltip('cost', title='Price (£m)', format='.1f'),
                        alt.Tooltip('total_points', title='Points'),
                        alt.Tooltip('ppm', title='PPM', format='.2f'),
                        alt.Tooltip('next_3_fixtures', title='Next 3 Fixtures')
                    ]
                )
                .properties(height=450)
                .interactive()
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No players match the selected criteria.")

        # Data table
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

        # Fixture Difficulty Rating Ranking
        st.subheader("Fixture Difficulty Rating - Next 3 Gameweeks")
        fdr_cols = [
            'photo_url',
            'web_name',
            'team_name',
            'position',
            'points_per_game',
            'fixture_ease_score',
            'fixture_difficulty_rating',
            'next_3_fixtures'
        ]
        st.dataframe(
            display_df[fdr_cols].sort_values('fixture_difficulty_rating', ascending=False).head(25),
            column_config={
                "photo_url": st.column_config.ImageColumn("Player", width="small"),
                "points_per_game": st.column_config.NumberColumn("Points/Game", format="%.2f"),
                "fixture_ease_score": st.column_config.NumberColumn("Fixture Ease", format="%.2f"),
                "fixture_difficulty_rating": st.column_config.NumberColumn("Fixture Difficulty Rating", format="%.2f"),
                "next_3_fixtures": st.column_config.TextColumn("Next 3 Fixtures"),
            },
            use_container_width=True,
            hide_index=True
        )

        # Team of the Week Section
        st.subheader("Team of the Week")
        recent_events = events_df[events_df['finished'] == True].sort_values('id', ascending=False).head(5)
        if recent_events.empty:
            st.info("Team of the Week data will be available once the season has progressed.")
        else:
            gw_options = recent_events['id'].tolist()
            gw_display = st.select_slider(
                "Scroll through the last five Gameweeks",
                options=gw_options,
                value=gw_options[0],
                format_func=lambda gw: f"GW {gw}"
            )
            lineup = build_team_of_week(gw_display, df)
            if lineup.empty:
                st.warning("Unable to build a team for that gameweek right now.")
            else:
                total_points = lineup['gw_points'].sum()
                st.metric("Total Points", f"{total_points:.0f}")
                render_lineup(lineup, gw_display)

    with tab2:
        st.subheader("🤖 Auto-Pick Dream Team")

        budget = st.slider("Team Budget (£m)", 80.0, 105.0, 100.0)
        formation = st.selectbox("Formation", ["3-4-3", "3-5-2", "4-4-2", "4-3-3"])

        if st.button("Generate Team"):
            defs, mids, fwds = map(int, formation.split("-"))
            gkps = 1

            def pick_best(pos_name, count, current_team):
                available = df[df['position'] == pos_name].sort_values('total_points', ascending=False)
                picked = []
                for _, player in available.iterrows():
                    if len(picked) < count:
                        picked.append(player)
                return picked

            squad = []
            squad += pick_best('GKP', gkps, squad)
            squad += pick_best('DEF', defs, squad)
            squad += pick_best('MID', mids, squad)
            squad += pick_best('FWD', fwds, squad)

            squad_df = pd.DataFrame(squad)

            total_points = squad_df['total_points'].sum()
            total_cost = squad_df['cost'].sum()

            col1, col2 = st.columns(2)
            col1.metric("Projected Points", int(total_points))
            col2.metric("Total Cost", f"£{total_cost:.1f}m", delta=f"{budget - total_cost:.1f}m left")

            st.dataframe(
                squad_df[['web_name', 'position', 'team_name', 'total_points', 'cost']],
                use_container_width=True
            )

elif page == "Player Compare":
    st.header("🔍 Player Compare")
    st.caption("Pick two players to compare their advanced metrics.")

    compare_choices = st.multiselect(
        "Select exactly two players",
        options=df['web_name'].sort_values().unique(),
        max_selections=2
    )

    if len(compare_choices) == 2:
        compare_df = df[df['web_name'].isin(compare_choices)].copy()
        radar_metrics = ['creativity', 'influence', 'threat', 'ict_index', 'points_per_game']

        # Ensure numeric and normalize 0-100
        metric_values = compare_df[radar_metrics].apply(pd.to_numeric, errors='coerce').fillna(0)
        min_vals = metric_values.min()
        max_vals = metric_values.max()
        ranges = (max_vals - min_vals).replace(0, 1)
        normalized = ((metric_values - min_vals) / ranges * 100).fillna(0)
        normalized['web_name'] = compare_df['web_name'].values

        radar_data = normalized.melt(id_vars='web_name', var_name='Metric', value_name='Value')

        fig = px.line_polar(
            radar_data,
            r='Value',
            theta='Metric',
            color='web_name',
            line_close=True,
            markers=True,
            range_r=[0, 100],
            template='plotly_dark'
        )
        fig.update_traces(fill='toself', opacity=0.4)
        st.plotly_chart(fig, use_container_width=True)

        compare_summary = compare_df[['web_name', 'now_cost', 'selected_by_percent', 'total_points']].copy()
        compare_summary['now_cost'] = compare_summary['now_cost'] / 10
        compare_summary = compare_summary.rename(columns={
            'web_name': 'Player',
            'now_cost': 'Price (£m)',
            'selected_by_percent': 'Ownership %',
            'total_points': 'Points'
        })
        st.dataframe(compare_summary.reset_index(drop=True), use_container_width=True)
    else:
        st.info("Select two players above to compare their stats.")

elif page == "League Spy":
    st.header("🕵️ League Spy")
    st.caption("Peek into any classic league and see how the leaders are doing.")

    league_id = st.text_input("League ID", "314")

    if st.button("Analyze League"):
        standings_url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
        try:
            response = requests.get(standings_url, timeout=10)
            response.raise_for_status()
            league_data = response.json()
            standings = league_data.get('standings', {}).get('results', [])

            if standings:
                standings_df = pd.DataFrame(standings)[['rank', 'player_name', 'entry_name', 'total']]
                standings_df = standings_df.rename(columns={
                    'rank': 'Rank',
                    'player_name': 'Player Name',
                    'entry_name': 'Team Name',
                    'total': 'Total Points'
                })

                top10_points = standings_df.head(10)['Total Points']
                avg_points = top10_points.mean() if not top10_points.empty else 0

                col1, col2 = st.columns(2)
                col1.metric("Top 10 Avg Points", f"{avg_points:.1f}")
                col2.metric("Teams Analyzed", len(standings_df))

                st.dataframe(standings_df, use_container_width=True, hide_index=True)
            else:
                st.warning("No standings data found for this league.")
        except requests.RequestException as e:
            st.error(f"Failed to load league data: {e}")
        except ValueError:
            st.error("Unable to parse league data.")

elif page == "Form Tracker":
    st.header("📈 Form Tracker")
    st.caption("Track recent gameweek form for your shortlisted players.")

    player_options = df[['id', 'web_name']].drop_duplicates().sort_values('web_name')
    selected_players = st.multiselect(
        "Select up to five players",
        options=player_options['web_name'],
        default=[],
        max_selections=5
    )

    show_cumulative = st.checkbox("Show Cumulative Points", value=False)

    if selected_players:
        histories = []
        for name in selected_players:
            player_row = player_options[player_options['web_name'] == name].iloc[0]
            player_id = player_row['id']
            try:
                summary = fetch_player_history(player_id)
                history = summary.get('history', [])
                if history:
                    hist_df = pd.DataFrame(history)[['round', 'total_points']].rename(columns={
                        'round': 'Gameweek',
                        'total_points': 'Points'
                    })
                    hist_df['Player'] = name
                    histories.append(hist_df)
            except requests.RequestException as e:
                st.error(f"Failed to fetch history for {name}: {e}")

        if histories:
            form_df = pd.concat(histories, ignore_index=True)
            if show_cumulative:
                form_df['Points'] = form_df.sort_values('Gameweek').groupby('Player')['Points'].cumsum()

            chart = (
                alt.Chart(form_df)
                .mark_line(point=True)
                .encode(
                    x=alt.X('Gameweek:O', title='Gameweek'),
                    y=alt.Y('Points:Q', title='Cumulative Points' if show_cumulative else 'Points'),
                    color='Player:N',
                    tooltip=['Player', 'Gameweek', 'Points']
                )
                .properties(height=450)
                .interactive()
            )
            st.altair_chart(chart, use_container_width=True)
            st.dataframe(form_df.sort_values(['Player', 'Gameweek']), use_container_width=True)
        else:
            st.info("No history data available for the selected players.")
    else:
        st.info("Select players above to view their form.")
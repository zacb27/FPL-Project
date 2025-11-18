import requests
import pandas as pd

# Position mapping
POSITIONS = {
    1: 'Goalkeeper',
    2: 'Defender',
    3: 'Midfielder',
    4: 'Forward'
}

def fetch_fpl_data():
    """Fetch data from FPL API"""
    url = 'https://fantasy.premierleague.com/api/bootstrap-static/'
    response = requests.get(url)
    response.raise_for_status()  # Raise error if request fails
    return response.json()

def process_player_data(data):
    """Process and enrich player data with additional stats"""
    players = pd.DataFrame(data['elements'])
    teams = pd.DataFrame(data['teams'])
    
    # Create team lookup
    team_lookup = teams.set_index('id')['name']
    
    # Create position lookup
    position_types = pd.DataFrame(data['element_types'])
    position_lookup = position_types.set_index('id')['singular_name']
    
    # Enrich player data
    players['Name'] = players['first_name'] + ' ' + players['second_name']
    players['Team'] = players['team'].map(team_lookup)
    players['Position'] = players['element_type'].map(position_lookup)
    players['Cost'] = players['now_cost'] / 10  # Convert to actual price
    
    # Calculate key metrics
    players['PPM'] = players['total_points'] / players['now_cost']  # Points per Million
    # Calculate games played - check for 'matches' field first, otherwise estimate from minutes
    if 'matches' in players.columns:
        players['games_played'] = players['matches'].replace(0, 1)
    else:
        # Estimate from minutes (assuming ~90 min per game)
        players['games_played'] = (players['minutes'] / 90).round().replace(0, 1)
    players['PPG'] = players['total_points'] / players['games_played']  # Points per Game
    players['Points_per_90'] = (players['total_points'] / players['minutes'].replace(0, 1)) * 90
    
    # Calculate value metrics
    players['Value'] = players['total_points'] / players['Cost']
    players['Form_Value'] = players['form'].astype(float) / players['Cost']
    
    # Calculate attacking stats per 90
    players['Goals_per_90'] = (players['goals_scored'] / players['minutes'].replace(0, 1)) * 90
    players['Assists_per_90'] = (players['assists'] / players['minutes'].replace(0, 1)) * 90
    players['G+A_per_90'] = players['Goals_per_90'] + players['Assists_per_90']
    
    # Calculate defensive stats per 90
    players['Clean_Sheets_per_90'] = (players['clean_sheets'] / players['minutes'].replace(0, 1)) * 90
    players['Saves_per_90'] = (players['saves'] / players['minutes'].replace(0, 1)) * 90
    
    return players

def filter_players(players, position=None, min_minutes=0, max_cost=None, min_cost=None):
    """Filter players based on criteria"""
    filtered = players.copy()
    
    if position:
        if isinstance(position, str):
            # Find position ID from name
            position_id = [k for k, v in POSITIONS.items() if v.lower() == position.lower() or position.lower() in v.lower()]
            if position_id:
                filtered = filtered[filtered['element_type'] == position_id[0]]
            else:
                filtered = filtered[filtered['Position'].str.contains(position, case=False, na=False)]
        else:
            filtered = filtered[filtered['element_type'] == position]
    
    if min_minutes > 0:
        filtered = filtered[filtered['minutes'] >= min_minutes]
    
    if max_cost:
        filtered = filtered[filtered['Cost'] <= max_cost]
    
    if min_cost:
        filtered = filtered[filtered['Cost'] >= min_cost]
    
    return filtered

def get_top_players(players, sort_by='PPM', top_n=15, ascending=False):
    """Get top N players sorted by specified metric"""
    return players.nlargest(top_n, sort_by) if ascending == False else players.nsmallest(top_n, sort_by)

def analyze_position(players, position_name, min_minutes=500, max_cost=None, top_n=15):
    """Analyze players in a specific position"""
    position_players = filter_players(players, position=position_name, min_minutes=min_minutes, max_cost=max_cost)
    
    if len(position_players) == 0:
        print(f"\nNo {position_name}s found with the specified criteria.")
        return None
    
    # Select relevant columns based on position
    if position_name.lower() in ['goalkeeper', 'defender']:
        cols = ['Name', 'Team', 'Position', 'Cost', 'total_points', 'PPG', 'PPM', 
                'Clean_Sheets_per_90', 'minutes', 'selected_by_percent']
    elif position_name.lower() == 'forward':
        cols = ['Name', 'Team', 'Position', 'Cost', 'total_points', 'PPG', 'PPM',
                'Goals_per_90', 'Assists_per_90', 'G+A_per_90', 'minutes', 'selected_by_percent']
    else:  # Midfielder
        cols = ['Name', 'Team', 'Position', 'Cost', 'total_points', 'PPG', 'PPM',
                'Goals_per_90', 'Assists_per_90', 'G+A_per_90', 'minutes', 'selected_by_percent']
    
    # Get available columns
    available_cols = [col for col in cols if col in position_players.columns]
    position_summary = position_players[available_cols].copy()
    
    # Rename columns for better display
    position_summary = position_summary.rename(columns={
        'total_points': 'Points',
        'selected_by_percent': 'Ownership %',
        'minutes': 'Minutes'
    })
    
    top_players = get_top_players(position_summary, sort_by='PPM', top_n=top_n)
    
    return top_players

def display_all_positions(players, min_minutes=500, max_cost=None, top_n=10):
    """Display top players for all positions"""
    print("=" * 80)
    print("FPL PLAYER ANALYSIS - TOP PLAYERS BY POSITION")
    print("=" * 80)
    
    for pos_id, pos_name in POSITIONS.items():
        print(f"\n{'=' * 80}")
        print(f"TOP {top_n} {pos_name.upper()}S (sorted by Points per Million)")
        print(f"{'=' * 80}")
        
        top_pos = analyze_position(players, pos_name, min_minutes=min_minutes, max_cost=max_cost, top_n=top_n)
        
        if top_pos is not None:
            print(top_pos.reset_index(drop=True).to_string(index=False))
        else:
            print(f"No {pos_name}s found with the specified criteria.")

# Main execution
if __name__ == "__main__":
    print("Fetching FPL data...")
    data = fetch_fpl_data()
    
    print("Processing player data...")
    players = process_player_data(data)
    
    print(f"\nTotal players loaded: {len(players)}")
    print(f"Players with >500 minutes: {len(players[players['minutes'] > 500])}")
    
    # Display top players by position
    display_all_positions(players, min_minutes=500, top_n=10)
    
    # Example: Find best value midfielders under £7.0m
    print("\n" + "=" * 80)
    print("BEST VALUE MIDFIELDERS (Under £7.0m, >500 minutes)")
    print("=" * 80)
    value_mids = analyze_position(players, 'Midfielder', min_minutes=500, max_cost=7.0, top_n=15)
    if value_mids is not None:
        print(value_mids.reset_index(drop=True).to_string(index=False))


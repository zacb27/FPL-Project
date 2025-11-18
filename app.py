from flask import Flask, render_template, request, jsonify
from scout import fetch_fpl_data, process_player_data, filter_players, get_top_players, analyze_position, POSITIONS
import pandas as pd

app = Flask(__name__)

# Cache for player data (refresh on each request for now, can be improved with caching)
def get_players_data():
    """Fetch and process FPL player data"""
    data = fetch_fpl_data()
    players = process_player_data(data)
    return players

@app.route('/')
def index():
    """Main page showing top players by position"""
    players = get_players_data()
    
    # Get filter parameters
    min_minutes = int(request.args.get('min_minutes', 500))
    max_cost = request.args.get('max_cost', None)
    max_cost = float(max_cost) if max_cost else None
    
    # Get top players for each position
    position_data = {}
    for pos_id, pos_name in POSITIONS.items():
        top_players = analyze_position(players, pos_name, min_minutes=min_minutes, max_cost=max_cost, top_n=15)
        if top_players is not None:
            # Convert to dict for template
            position_data[pos_name] = top_players.to_dict('records')
        else:
            position_data[pos_name] = []
    
    return render_template('index.html', 
                         position_data=position_data,
                         min_minutes=min_minutes,
                         max_cost=max_cost,
                         positions=POSITIONS)

@app.route('/api/players')
def api_players():
    """API endpoint for player data with filtering"""
    players = get_players_data()
    
    # Get filter parameters
    position = request.args.get('position', None)
    min_minutes = int(request.args.get('min_minutes', 0))
    max_cost = request.args.get('max_cost', None)
    max_cost = float(max_cost) if max_cost else None
    min_cost = request.args.get('min_cost', None)
    min_cost = float(min_cost) if min_cost else None
    sort_by = request.args.get('sort_by', 'PPM')
    top_n = int(request.args.get('top_n', 50))
    
    # Filter players
    filtered = filter_players(players, position=position, min_minutes=min_minutes, 
                             max_cost=max_cost, min_cost=min_cost)
    
    # Sort and get top N
    if len(filtered) > 0:
        top_players = get_top_players(filtered, sort_by=sort_by, top_n=top_n)
        # Convert to JSON-friendly format
        result = top_players.to_dict('records')
        # Replace NaN with None for JSON serialization
        for record in result:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None
        return jsonify(result)
    else:
        return jsonify([])

@app.route('/position/<position_name>')
def position_page(position_name):
    """Page for specific position"""
    players = get_players_data()
    
    # Get filter parameters
    min_minutes = int(request.args.get('min_minutes', 500))
    max_cost = request.args.get('max_cost', None)
    max_cost = float(max_cost) if max_cost else None
    top_n = int(request.args.get('top_n', 20))
    
    # Get players for this position
    position_players = analyze_position(players, position_name, min_minutes=min_minutes, 
                                       max_cost=max_cost, top_n=top_n)
    
    if position_players is not None:
        players_list = position_players.to_dict('records')
        # Replace NaN with None
        for record in players_list:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None
    else:
        players_list = []
    
    return render_template('position.html',
                         position_name=position_name,
                         players=players_list,
                         min_minutes=min_minutes,
                         max_cost=max_cost,
                         top_n=top_n)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



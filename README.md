# FPL Vibe - Fantasy Premier League Tracker

A web application for tracking and analyzing Fantasy Premier League players. Find the best value players by position with detailed statistics and filtering options.

## Features

- 📊 **Player Analysis**: View top players by position (Goalkeepers, Defenders, Midfielders, Forwards)
- 🔍 **Advanced Filtering**: Filter by minimum minutes played, maximum cost, and more
- 📈 **Key Metrics**: Points per Million (PPM), Points per Game (PPG), Goals/Assists per 90, and more
- 🎨 **Modern UI**: Clean, responsive design with easy-to-read tables
- ⚡ **Real-time Data**: Fetches live data from the official FPL API

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

1. Start the Flask server:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

## Usage

### Home Page
- View top players across all positions
- Use filters to adjust minimum minutes and maximum cost
- Click "View All" to see more players in a specific position

### Position Pages
- Detailed view of players in a specific position
- Adjustable filters for minutes, cost, and number of results
- Sortable tables with all relevant statistics

### API Endpoint
Access player data via JSON API:
```
/api/players?position=Midfielder&min_minutes=500&max_cost=7.0&sort_by=PPM&top_n=20
```

## Project Structure

```
FPL-Vibe code/
├── app.py              # Flask application
├── scout.py            # Core FPL data processing functions
├── requirements.txt    # Python dependencies
├── templates/          # HTML templates
│   ├── base.html       # Base template
│   ├── index.html      # Home page
│   └── position.html   # Position-specific page
└── static/             # Static files
    └── style.css       # Stylesheet
```

## Technologies Used

- **Flask**: Web framework
- **Pandas**: Data processing and analysis
- **Requests**: API calls to FPL
- **HTML/CSS**: Frontend interface

## Data Source

All data is fetched from the official Fantasy Premier League API:
- https://fantasy.premierleague.com/api/bootstrap-static/

## License

This project is for personal use and educational purposes.



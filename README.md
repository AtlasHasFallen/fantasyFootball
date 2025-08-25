# Overview
This repository will primarily serve to pull and aggregate data from various sources to create a unified dataset of historical fantasy football data. The goal is to create a comprehensive dataset that can be used for analysis, modeling, and other purposes.

## Getting Started
Install dependencies (recommended: [UV](https://github.com/astral-sh/uv)):
```sh
uv sync
```
To add a new package:
```sh
uv add <package-name>
uv sync
```
Run the main script:
```sh
python main.py
```

## Requirements
- Python 3.10+
- UV (package management)
- Ruff (linting)
- pyproject.toml (for dependencies)

## Project Structure
- `main.py`: Entry point
- `score_calculator`: Fantasy points logic
- `data_aggregator`: Data collection & aggregation
- `data_cleaner`: Data cleaning & output

# League Settings
The scoring for the League I am in is at the following URL: https://fantasy.espn.com/football/league/settings?leagueId=970286&seasonId=2025&view=scoring

The roster settings for the League I am in is at the following URL: https://fantasy.espn.com/football/league/settings?leagueId=970286&seasonId=2025&view=rosters

# Modules
The module called score_calulator contains the logic to calculate the fantasy points for each player based on the league settings. The module is designed to be flexible and can be easily modified to accommodate different league settings.

The module called data_aggregator contains the logic to pull data from various sources and aggregate it into a unified dataset. The module is designed to be flexible and can be easily modified to accommodate different data sources. The module will only pull data for the players that will be playing in the upcoming season based on the league settings.

The module called data_cleaner contains the logic to clean and preprocess the data. The module will calculate the fantasy points for each player based on the league settings. The final output will be a cleaned and preprocessed dataset that can be used for analysis, modeling, and other purposes. The output will be saved as a parquet file.

## Output
The final dataset is saved as a parquet file for analysis and modeling.

## License
MIT

## Contributing
Pull requests and issues are welcome.
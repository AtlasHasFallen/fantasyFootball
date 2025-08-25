"""
Module: nfl_roster_fetcher.py
Fetches and saves the complete NFL roster for the current season (2025) from the official NFL website.
"""

import requests
import polars as pl
import os
from bs4 import BeautifulSoup

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
CSV_PATH = os.path.join(DATA_DIR, 'nfl_roster_2025.csv')
NFL_TEAMS_URL = 'https://www.nfl.com/teams/'


def fetch_team_urls():
    """Fetches all NFL team URLs from the NFL teams page."""
    try:
        resp = requests.get(NFL_TEAMS_URL)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching NFL teams page: {e}")
        return []
    soup = BeautifulSoup(resp.text, 'html.parser')
    all_links = soup.find_all('a')
    team_hrefs = [link.get('href', '') for link in all_links if link.get('href', '').startswith('/teams/') and link.get('href', '').endswith('/')]    
    print(f"Found {len(team_hrefs)} NFL teams.")
    urls = [f"https://www.nfl.com{href}roster/" for href in team_hrefs]
    return urls


def fetch_roster_for_team(team_url):
    """Fetches roster for a single team."""
    try:
        resp = requests.get(team_url)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching team roster page {team_url}: {e}")
        return [], []
    soup = BeautifulSoup(resp.text, 'html.parser')
    table = soup.find('table')
    if not table:
        print(f"No roster table found for {team_url}")
        return [], []
    headers = [th.text.strip() for th in table.find('thead').find_all('th')]
    rows = []
    for tr in table.find('tbody').find_all('tr'):
        row = [td.text.strip() for td in tr.find_all('td')]
        rows.append(row)
    print(f"Found {len(rows)} players for {team_url}")
    return headers, rows


def fetch_and_save_nfl_roster():
    """Fetches all NFL rosters and saves as a CSV file using polars. Creates data folder if missing. Logs errors and progress."""
    try:
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            print(f"Created data directory at {DATA_DIR}")
    except Exception as e:
        print(f"Error creating data directory: {e}")
        return
    all_players = []
    headers = None
    team_urls = fetch_team_urls()
    if not team_urls:
        print("No team URLs found. Exiting.")
        return
    for team_url in team_urls:
        h, rows = fetch_roster_for_team(team_url)
        if not h or not rows:
            print(f"Skipping team {team_url} due to missing data.")
            continue
        if headers is None:
            headers = h + ['Team']
        team_name = team_url.split('/')[4].replace('-', ' ').title()
        for row in rows:
            all_players.append(row + [team_name])
        print(f"Fetched {len(rows)} players for {team_name}")
    if not all_players or not headers:
        print("No player data collected. Exiting.")
        return
    try:
        df = pl.DataFrame(all_players, schema=headers, orient='row')
        df.write_csv(CSV_PATH)
        print(f'NFL roster saved to {CSV_PATH}')
    except Exception as e:
        print(f"Error saving CSV: {e}")

# Example usage:
fetch_and_save_nfl_roster()

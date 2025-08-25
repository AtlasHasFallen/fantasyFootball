"""
Module: historical_data_fetcher.py
Fetches and saves NFL player and team stats for the last 5 seasons (2020-2024) from Pro Football Reference.
"""

import requests
import polars as pl
import os
from bs4 import BeautifulSoup

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
SEASONS = [2020, 2021, 2022, 2023, 2024]
PFR_BASE = 'https://www.pro-football-reference.com'
PLAYER_STATS_URL = PFR_BASE + '/years/{year}/fantasy.htm'
TEAM_STATS_URL = PFR_BASE + '/years/{year}/'


def fetch_table(url, table_id):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    table = soup.find('table', id=table_id)
    if not table:
        print(f"No table with id '{table_id}' found at {url}")
        return None, None
    headers = [th.text.strip() for th in table.find('thead').find_all('th')]
    rows = []
    for tr in table.find('tbody').find_all('tr'):
        row = [td.text.strip() for td in tr.find_all('td')]
        if row:
            rows.append(row)
    return headers, rows


def fetch_and_save_stats():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    for year in SEASONS:
        # Player stats
        player_url = PLAYER_STATS_URL.format(year=year)
        headers, rows = fetch_table(player_url, 'fantasy')
        if headers and rows:
            df = pl.DataFrame(rows, schema=headers, orient='row')
            out_path = os.path.join(DATA_DIR, f'nfl_player_stats_{year}.csv')
            df.write_csv(out_path)
            print(f"Saved player stats for {year} to {out_path}")
        else:
            print(f"No player stats for {year}")
        # Team stats
        team_url = TEAM_STATS_URL.format(year=year)
        headers, rows = fetch_table(team_url, 'team_stats')
        if headers and rows:
            df = pl.DataFrame(rows, schema=headers, orient='row')
            out_path = os.path.join(DATA_DIR, f'nfl_team_stats_{year}.csv')
            df.write_csv(out_path)
            print(f"Saved team stats for {year} to {out_path}")
        else:
            print(f"No team stats for {year}")

# Example usage:
fetch_and_save_stats()

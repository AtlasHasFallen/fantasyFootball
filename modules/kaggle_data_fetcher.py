"""
Module: kaggle_data_fetcher.py
Downloads NFL play-by-play data from Kaggle using the Kaggle API and saves it to the data folder.
"""

import os
import subprocess

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
KAGGLE_CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
KAGGLE_DATASET = 'maxhorowitz/nflplaybyplay2009'


def fetch_kaggle_nfl_data():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    os.environ['KAGGLE_CONFIG_DIR'] = KAGGLE_CONFIG_DIR
    datasets = [
        'philiphyde1/nfl-stats-1999-2022',
        'nickcantalupa/nfl-team-data-2003-2023',
        'rishabjadhav/nfl-passing-statistics-2001-2023',
        'dtrade84/nfl-offensive-stats-2019-2022',
    ]
    for dataset in datasets:
        print(f"Downloading {dataset} to {DATA_DIR}...")
        result = subprocess.run([
            'kaggle', 'datasets', 'download', '-d', dataset,
            '-p', DATA_DIR, '--unzip'
        ], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Download of {dataset} complete.")
        else:
            print(f"Error downloading {dataset}: {result.stderr}")

# Example usage:
fetch_kaggle_nfl_data()

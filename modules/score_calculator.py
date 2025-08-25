"""
score_calculator.py
Flexible module for calculating fantasy football points based on league settings.
"""

import yaml
from typing import Dict, Any

class ScoreCalculator:
    def __init__(self, scoring_rules: Dict[str, float]):
        """
        scoring_rules: dict mapping stat names to point values
        Example: {'passing_td': 4, 'rushing_td': 6, 'reception': 1}
        """
        self.scoring_rules = scoring_rules

    def calculate_player_score(self, stats: Dict[str, Any]) -> float:
        """
        Calculate fantasy points for a player given their stats.
        stats: dict mapping stat names to values
        Returns: total fantasy points (float)
        """
        score = 0.0
        for stat, value in stats.items():
            points = self.scoring_rules.get(stat, 0)
            score += points * value
        return score


def load_scoring_rules_from_yaml(yaml_path: str) -> Dict[str, float]:
    """
    Loads scoring rules from a YAML file with categories.
    Flattens the categories into a single dict.
    """
    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)
    flat_rules = {}
    for category, rules in config.items():
        flat_rules.update(rules)
    return flat_rules

# Example usage:
# yaml_path = 'modules/scoring_config.yaml'
# scoring = load_scoring_rules_from_yaml(yaml_path)
# stats = {'PTD': 2, 'PY25': 10, 'INT': 1}
# calc = ScoreCalculator(scoring)
# print(calc.calculate_player_score(stats))

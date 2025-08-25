# Fantasy Football League Scoring Settings
# This config can be loaded and passed to ScoreCalculator
scoring_rules = {
    "passing_yds": 0.04,      # 1 pt per 25 passing yards
    "passing_td": 4.0,        # 4 pts per passing TD
    "interception": -2.0,     # -2 pts per interception
    "rushing_yds": 0.1,       # 1 pt per 10 rushing yards
    "rushing_td": 6.0,        # 6 pts per rushing TD
    "reception": 1.0,         # 1 pt per reception (PPR)
    "receiving_yds": 0.1,     # 1 pt per 10 receiving yards
    "receiving_td": 6.0,      # 6 pts per receiving TD
    "fumble_lost": -2.0,      # -2 pts per fumble lost
    "two_pt_conv": 2.0,       # 2 pts per two-point conversion
    # Add more as needed
}

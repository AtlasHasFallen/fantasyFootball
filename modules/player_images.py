"""player_images

Download NFL player face images (headshots) for all players in the roster CSV.

Current implementation uses the public Sleeper API which provides headshot URLs
without requiring authentication.

Sleeper API endpoint:
  https://api.sleeper.app/v1/players/nfl  (returns one large JSON object)

For each roster player we attempt to find a matching Sleeper player entry by
normalized full name and (if present) matching team code / position to disambiguate.

Saved images:
  data/headshots/<player_id>.jpg  (Sleeper player_id to avoid name collisions)

Also writes a mapping file:
  data/headshots/_mapping.parquet with columns:
      player_id, full_name, team, position, image_path, source

Usage examples:
  python modules/player_images.py --roster data/nfl_roster_2025.csv
  python modules/player_images.py --roster data/nfl_roster_2025.csv --limit 25 --verbose
  python modules/player_images.py --roster data/nfl_roster_2025.csv --out-dir data/headshots --force

Dependencies: requests, polars (already in project requirements).
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Dict, Tuple

import polars as pl
import requests

SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"


def _norm(name: str | None) -> str:
    if not name:
        return ""
    n = name.lower()
    n = re.sub(r"[\.'`,]", "", n)
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b$", "", n).strip()
    n = re.sub(r"\s+", " ", n)
    return n


def load_roster(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Roster file not found: {path}")
    df = pl.read_csv(path)
    # Find name column
    name_col = None
    lowered = {c.lower(): c for c in df.columns}
    for cand in ("player", "player_name", "name"):
        if cand in lowered:
            name_col = lowered[cand]
            break
    if name_col is None:
        raise ValueError("No recognizable player name column in roster.")
    # Standardize name column label
    if name_col != "player_name":
        df = df.rename({name_col: "player_name"})
        name_col = "player_name"
    # Normalize a helper column
    df = df.with_columns(pl.col(name_col).cast(pl.Utf8).map_elements(_norm, return_dtype=pl.Utf8).alias("_norm_name"))
    # Optional position/team columns standardization
    for col in ("position", "pos"):
        if col in df.columns:
            df = df.rename({col: "position"})
            break
    if "team" in df.columns:
        df = df.with_columns(pl.col("team").cast(pl.Utf8).str.to_uppercase())
    return df


def fetch_sleeper_players() -> Dict[str, dict]:
    resp = requests.get(SLEEPER_PLAYERS_URL, timeout=60)
    resp.raise_for_status()
    return resp.json()  # keyed by sleeper player_id


def build_lookup(players_json: Dict[str, dict]) -> Dict[str, list[dict]]:
    lookup: Dict[str, list[dict]] = {}
    for pid, pdata in players_json.items():
        full = pdata.get("full_name") or pdata.get("first_name", "") + " " + pdata.get("last_name", "")
        norm = _norm(full)
        if not norm:
            continue
        pdata["player_id"] = pid
        lookup.setdefault(norm, []).append(pdata)
    return lookup


def choose_best_candidate(candidates: list[dict], roster_team: str | None, roster_pos: str | None) -> dict | None:
    if not candidates:
        return None
    # If only one, return it
    if len(candidates) == 1:
        return candidates[0]
    # Try exact team + position match
    for c in candidates:
        if roster_team and roster_pos and c.get("team") == roster_team and c.get("position") == roster_pos:
            return c
    # Team match
    if roster_team:
        for c in candidates:
            if c.get("team") == roster_team:
                return c
    # Position match
    if roster_pos:
        for c in candidates:
            if c.get("position") == roster_pos:
                return c
    # Fallback first
    return candidates[0]


def headshot_urls(pdata: dict) -> Tuple[str | None, str | None]:
    # Sleeper sometimes provides headshot_url directly; also construct canonical patterns
    direct = pdata.get("headshot_url")
    pid = pdata.get("player_id")
    if pid:
        # Known patterns (thumb and full). We'll prefer full if reachable.
        thumb = f"https://sleepercdn.com/content/nfl/players/thumb/{pid}.jpg"
        full = f"https://sleepercdn.com/content/nfl/players/full/{pid}.jpg"
        return direct or full, thumb
    return direct, None


def download_image(url: str, dest: Path, timeout: int = 30) -> bool:
    try:
        r = requests.get(url, timeout=timeout)
        if r.status_code == 200 and r.content and r.headers.get("Content-Type", "").startswith("image"):
            dest.write_bytes(r.content)
            return True
    except requests.RequestException:
        return False
    return False


def main():  # pragma: no cover
    parser = argparse.ArgumentParser(description="Download player headshots (Sleeper API)")
    parser.add_argument("--roster", type=str, default="data/nfl_roster_2025.csv", help="Path to roster CSV")
    parser.add_argument("--out-dir", type=str, default="data/headshots", help="Directory to store images")
    parser.add_argument("--limit", type=int, help="Only process the first N roster players (for testing)")
    parser.add_argument("--sleep", type=float, default=0.05, help="Sleep seconds between downloads to be polite")
    parser.add_argument("--force", action="store_true", help="Re-download even if image file exists")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    roster_path = Path(args.roster)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Fetching Sleeper players JSON (this is large; may take a few seconds)...")
    players_json = fetch_sleeper_players()
    lookup = build_lookup(players_json)
    print(f"Loaded {len(players_json)} Sleeper player entries; {len(lookup)} unique normalized names.")

    roster_df = load_roster(roster_path)
    if args.limit:
        roster_df = roster_df.head(args.limit)
    have_position = "position" in roster_df.columns
    have_team = "team" in roster_df.columns

    rows = []
    processed = 0
    downloaded = 0
    missing = 0
    for row in roster_df.iter_rows(named=True):
        norm_name = row["_norm_name"]
        team = row.get("team") if have_team else None
        pos = row.get("position") if have_position else None
        candidates = lookup.get(norm_name, [])
        sel = choose_best_candidate(candidates, team, pos)
        if not sel:
            missing += 1
            if args.verbose:
                print(f"[MISS] {row.get('player', row.get('player_name', norm_name))}")
            continue
        primary_url, thumb_url = headshot_urls(sel)
        # Determine filename
        pid = sel.get("player_id") or norm_name.replace(" ", "_")
        img_path = out_dir / f"{pid}.jpg"
        if img_path.exists() and not args.force:
            status = "cached"
        else:
            success = False
            tried = []
            for u in [primary_url, thumb_url]:
                if not u:
                    continue
                tried.append(u)
                if download_image(u, img_path):
                    success = True
                    break
            if success:
                downloaded += 1
                status = "downloaded"
            else:
                missing += 1
                status = "failed"
                if args.verbose:
                    print(f"[FAIL] {norm_name} urls={tried}")
                continue
            if args.sleep:
                time.sleep(args.sleep)
        if args.verbose:
            print(f"[OK] {norm_name} -> {img_path.name} ({status})")
        rows.append({
            "player_id": pid,
            "full_name": sel.get("full_name"),
            "team": sel.get("team"),
            "position": sel.get("position"),
            "image_path": str(img_path),
            "source": "sleeper",
        })
        processed += 1

    if rows:
        mapping_df = pl.DataFrame(rows)
        mapping_df.write_parquet(out_dir / "_mapping.parquet", compression="zstd")
        mapping_df.write_csv(out_dir / "_mapping.csv")
    print(f"Processed roster players: {processed}")
    print(f"Images downloaded: {downloaded}")
    print(f"Missing / failed: {missing}")
    if rows:
        print(f"Mapping written: {out_dir / '_mapping.parquet'}")


if __name__ == "__main__":  # pragma: no cover
    main()

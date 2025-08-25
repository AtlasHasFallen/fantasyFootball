"""data_cleaner

Utility functions to clean and standardize raw NFL CSV datasets.

Features:
 - File existence checks (avoids FileNotFound errors)
 - Column name normalization (snake_case)
 - Duplicate row removal
 - Numeric type inference (casts text columns to int/float when ≥90% numeric)
 - Null filling (numeric -> 0, others left as-is)
 - Automatic filtering of player-level stats to only 2025 roster players (if roster file present)
 - Batch mode to clean every CSV in data/ (excluding already cleaned/parquet outputs)

Usage examples (run from project root):
    python modules/data_cleaner.py --file data/team_stats_2003_2023.csv
    python modules/data_cleaner.py --all
    python modules/data_cleaner.py --all --consolidate-output data/clean/all_player_stats.parquet
    python modules/data_cleaner.py --list
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Set

import polars as pl
import yaml

DATA_DIR = Path("data")
OUTPUT_SUBDIR = DATA_DIR / "clean"
OUTPUT_SUBDIR.mkdir(parents=True, exist_ok=True)
ROSTER_FILE = DATA_DIR / "nfl_roster_2025.csv"


def _normalize_columns(cols: Iterable[str]) -> list[str]:
    return [c.strip().lower().replace(" ", "_").replace("/", "_") for c in cols]


def _normalize_player_name(name: str) -> str:
    import re
    # Lowercase, remove periods/commas/apostrophes, collapse spaces, strip suffixes Jr/III/etc.
    n = name.lower()
    n = re.sub(r"[\.'`,]", "", n)
    # Remove common suffixes at end
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b$", "", n).strip()
    n = re.sub(r"\s+", " ", n)
    return n


def load_roster_players() -> Set[str]:
    if not ROSTER_FILE.exists():
        return set()
    try:
        roster = pl.read_csv(ROSTER_FILE)
    except Exception:
        return set()
    # Accept either 'Player' or already normalized 'player'
    candidate_cols = [c for c in roster.columns if c.lower() in {"player", "player_name"}]
    if not candidate_cols:
        return set()
    col = candidate_cols[0]
    return { _normalize_player_name(str(v)) for v in roster[col].to_list() if v is not None }


def infer_numeric_types(df: pl.DataFrame, min_ratio: float = 0.9, sample_size: int = 5000) -> pl.DataFrame:
    import re
    numeric_pattern = re.compile(r"^-?\d+(\.\d+)?$")
    casts = []
    for col, dtype in zip(df.columns, df.dtypes):
        if str(dtype) != "Utf8":
            continue
        s = df[col]
        # sample values
        values = s.head(sample_size).to_list()
        non_empty = [v for v in values if v not in (None, "")]
        if not non_empty:
            continue
        matches = 0
        any_float = False
        for v in non_empty:
            vs = str(v).strip()
            if numeric_pattern.match(vs):
                matches += 1
                if "." in vs:
                    any_float = True
            else:
                # allow trailing .0
                if numeric_pattern.match(vs.rstrip("0").rstrip(".")):
                    matches += 1
                    any_float = True
        ratio = matches / len(non_empty)
        if ratio >= min_ratio:
            target = pl.Float64 if any_float else pl.Int64
            casts.append(pl.col(col).cast(target, strict=False))
    if casts:
        df = df.with_columns(casts)
    return df


def clean_nfl_data(input_path: str | Path, output_path: str | Path, roster_players: Set[str] | None = None) -> Path:
    """Clean a single CSV file and write a Parquet output.

    Args:
        input_path: Path to raw CSV.
        output_path: Desired Parquet path.
    Returns:
        Path to written Parquet file.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Attempt standard read; on schema inference failure fall back to safe mode (all Utf8)
    try:
        df = pl.read_csv(input_path)
    except Exception as e:  # noqa: BLE001
        print(f"‣ Standard read failed for {input_path.name}: {e}\n  Falling back to safe all-text load.")
        with input_path.open('r', encoding='utf-8') as f:
            header = f.readline().rstrip('\n')
        cols = header.split(',')
        schema_overrides = {c: pl.Utf8 for c in cols}
        df = pl.read_csv(input_path, schema_overrides=schema_overrides, ignore_errors=False)

    # Dedupe
    df = df.unique()

    # Numeric inference BEFORE fill_null
    df = infer_numeric_types(df)

    # Fill numeric nulls with 0 only (avoid overwriting text fields)
    numeric_cols = [c for c, dt in zip(df.columns, df.dtypes) if getattr(dt, 'is_numeric', lambda: False)()]  # type: ignore
    if numeric_cols:
        df = df.with_columns([pl.col(c).fill_null(0) for c in numeric_cols])

    # Column normalization
    df.columns = _normalize_columns(df.columns)

    # Roster filter (only for player-level datasets when roster provided)
    if roster_players:
        # Attempt to find a player-name column.
        name_col = None
        for cand in ("player_name", "player", "name"):
            if cand in df.columns:
                name_col = cand
                break
        if name_col:
            pre_rows = df.height
            df = df.with_columns(
                pl.col(name_col)
                .cast(pl.Utf8)
                .map_elements(lambda s: _normalize_player_name(s) if s is not None else s, return_dtype=pl.Utf8)
                .alias("_norm_player")
            ).filter(pl.col("_norm_player").is_in(list(roster_players))).drop("_norm_player")
            post_rows = df.height
            print(f"  Roster filter applied ({name_col}): {pre_rows} -> {post_rows} rows")

    # Write parquet
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(output_path)
    print(f"✔ Cleaned {input_path.name} -> {output_path.relative_to(Path.cwd()) if output_path.is_absolute() else output_path}")
    return output_path


def discover_raw_csvs() -> list[Path]:
    """Return list of candidate raw CSV files in data/ excluding roster (different schema) and already cleaned outputs."""
    csvs: list[Path] = []
    for p in DATA_DIR.glob("*.csv"):
        if p.name.endswith("_cleaned.csv"):
            continue
        if p.name.startswith("nfl_roster"):
            continue
        csvs.append(p)
    return sorted(csvs)


def batch_clean(roster_players: Set[str]) -> list[Path]:
    outputs: list[Path] = []
    for csv in discover_raw_csvs():
        out = OUTPUT_SUBDIR / (csv.stem + ".parquet")
        try:
            outputs.append(clean_nfl_data(csv, out, roster_players))
        except Exception as e:  # noqa: BLE001
            print(f"✖ Failed to clean {csv.name}: {e}")
    return outputs


def consolidate_player_stats(
    output_path: Path,
    pattern: str = "player_stats",
    mode: str = "intersection",
    dedupe_keys: list[str] | None = None,
) -> Path:
    """Combine cleaned player-level parquet files into a single large parquet.

    Args:
        output_path: target parquet file path
        pattern: substring that must appear in filename to be included
        mode: 'intersection' keeps only columns present in all files (stable); 'union' adds missing columns as nulls.
    """
    parquet_files = [p for p in OUTPUT_SUBDIR.glob("*.parquet") if pattern in p.name]
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files in {OUTPUT_SUBDIR} matching pattern '{pattern}'.")
    dfs = [pl.read_parquet(p) for p in parquet_files]
    if mode not in {"intersection", "union"}:
        raise ValueError("mode must be 'intersection' or 'union'")
    if mode == "intersection":
        common_cols = set(dfs[0].columns)
        for d in dfs[1:]:
            common_cols &= set(d.columns)
        common_cols = sorted(common_cols)
        # Collect dtypes; if mismatched across dataframes, cast to Utf8
        dtype_map: dict[str, set[str]] = {c: set() for c in common_cols}
        for d in dfs:
            for c, dt in zip(d.columns, d.dtypes):
                if c in dtype_map:
                    dtype_map[c].add(str(dt))
        cast_cols = {c for c, dts in dtype_map.items() if len(dts) > 1}
        aligned = []
        for d in dfs:
            sel = d.select(common_cols)
            if cast_cols:
                sel = sel.with_columns([pl.col(c).cast(pl.Utf8, strict=False) for c in cast_cols])
            aligned.append(sel)
        dfs = aligned
    else:  # union
        # Order-preserving union of columns
        all_cols: list[str] = []
        seen: set[str] = set()
        for d in dfs:
            for c in d.columns:
                if c not in seen:
                    seen.add(c)
                    all_cols.append(c)
        # Build global dtype map to decide target dtype per column
        dtype_map: dict[str, set[str]] = {c: set() for c in all_cols}
        for d in dfs:
            for c, dt in zip(d.columns, d.dtypes):
                dtype_map[c].add(str(dt))
        numeric_tokens = {"Int8","Int16","Int32","Int64","UInt8","UInt16","UInt32","UInt64","Float32","Float64"}
        target_numeric: dict[str, bool] = {c: any(dt in numeric_tokens for dt in dts) for c, dts in dtype_map.items()}
        aligned: list[pl.DataFrame] = []
        for d in dfs:
            # Add any missing columns first with typed nulls
            missing = [c for c in all_cols if c not in d.columns]
            if missing:
                add_exprs = []
                for c in missing:
                    if target_numeric[c]:
                        add_exprs.append(pl.lit(None).cast(pl.Float64).alias(c))
                    else:
                        add_exprs.append(pl.lit(None).cast(pl.Utf8).alias(c))
                d = d.with_columns(add_exprs)
            # Cast existing columns to target dtype
            cast_exprs = []
            for c in all_cols:
                if target_numeric[c]:
                    cast_exprs.append(pl.col(c).cast(pl.Float64, strict=False))
                else:
                    cast_exprs.append(pl.col(c).cast(pl.Utf8, strict=False))
            d = d.select(cast_exprs)
            aligned.append(d)
        dfs = aligned
    combined = pl.concat(dfs, how="vertical", rechunk=True)
    if dedupe_keys:
        existing_keys = [k for k in dedupe_keys if k in combined.columns]
        # remove duplicates while preserving order
        existing_keys = list(dict.fromkeys(existing_keys))
        if existing_keys:
            before = combined.height
            combined = combined.unique(subset=existing_keys, keep="first")
            after = combined.height
            print(f"✔ Dedupe applied on keys {existing_keys}: {before} -> {after} rows")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.write_parquet(output_path, compression="zstd")
    print(f"✔ Consolidated {len(parquet_files)} files -> {output_path} ({combined.height} rows, {combined.width} cols)")
    return output_path


def load_scoring_rules(yaml_path: Path = Path("config/scoring_config.yaml")) -> dict[str, float]:
    if not yaml_path.exists():
        raise FileNotFoundError(f"Scoring config not found: {yaml_path}")
    with yaml_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    flat: dict[str, float] = {}
    for cat, rules in cfg.items():
        if isinstance(rules, dict):
            for k, v in rules.items():
                try:
                    flat[k] = float(v)
                except (TypeError, ValueError):
                    pass
    return flat


def apply_fantasy_scoring(parquet_path: Path, output_path: Path | None = None) -> Path:
    """Compute fantasy points on consolidated player stats using scoring rules.

    Because raw granular stats (e.g. passing yards) may not be present in consolidated columns yet,
    we currently augment existing fantasy_points_ppr if available and apply additive modifiers for any
    overlapping stat tokens (INT, SF, FUML) that exist in scoring config and dataset.
    """
    df = pl.read_parquet(parquet_path)
    scoring = load_scoring_rules()
    available = set(df.columns)

    # Build expressions from available per-play/per-week stats if present
    exprs: list[pl.Expr] = []
    yardage_map = [
        ("passing_yards", "PY25", 1.0),
        ("rushing_yards", "RY10", 1.0),
        ("receiving_yards", "REY10", 1.0),
    ]
    for col, token, mult in yardage_map:
        if col in available and token in scoring:
            exprs.append(pl.col(col).cast(pl.Float64, strict=False) * scoring[token] * mult)

    td_map = [
        ("pass_touchdown", "PTD"),
        ("rush_touchdown", "RTD"),
        ("receiving_touchdown", "RETD"),
    ]
    for col, token in td_map:
        if col in available and token in scoring:
            exprs.append(pl.col(col).cast(pl.Float64, strict=False) * scoring[token])

    misc_map = [
        ("interception", "INT"),
        ("safety", "SF"),
        ("fumble_lost", "FUML"),
    ]
    for col, token in misc_map:
        if col in available and token in scoring:
            exprs.append(pl.col(col).cast(pl.Float64, strict=False) * scoring[token])

    if exprs:
        total_expr = sum(exprs).alias("fantasy_points_league_calc")
        df = df.with_columns(total_expr)
        if "week" in available:
            df = df.with_columns(pl.col("fantasy_points_league_calc").alias("fantasy_points_league"))
        else:
            if "fantasy_points_ppr" in available:
                df = df.with_columns(
                    (pl.col("fantasy_points_ppr").cast(pl.Float64, strict=False) + pl.col("fantasy_points_league_calc")).alias("fantasy_points_league")
                )
            else:
                df = df.rename({"fantasy_points_league_calc": "fantasy_points_league"})
    else:
        if "fantasy_points_ppr" in available:
            df = df.with_columns(pl.col("fantasy_points_ppr").cast(pl.Float64, strict=False).alias("fantasy_points_league"))
        else:
            print("(scoring) No applicable stats; leaving file unchanged.")
            return parquet_path
    out = output_path or parquet_path
    df.write_parquet(out, compression="zstd")
    print(f"✔ Applied fantasy scoring -> {out}")
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean NFL CSV datasets")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--file", type=str, help="Specific CSV file to clean")
    group.add_argument("--all", action="store_true", help="Clean all discovered CSV files")
    group.add_argument("--list", action="store_true", help="List discoverable raw CSV files")
    parser.add_argument("--consolidate-output", type=str, help="Optional: path to write a single consolidated player stats parquet after cleaning (matches '*player_stats*')")
    parser.add_argument("--no-auto-consolidate", action="store_true", help="Disable automatic consolidation after --all (default writes data/clean/all_player_stats.parquet)")
    parser.add_argument("--prune-matched", action="store_true", help="After consolidation: delete the individual parquet files that were merged.")
    parser.add_argument("--score", action="store_true", help="After consolidation (or when specifying --consolidate-output) apply fantasy scoring to the consolidated parquet.")
    parser.add_argument("--consolidation-mode", choices=["intersection", "union"], default="intersection", help="Column alignment mode for consolidation (default intersection). For weekly data choose union to retain 'week'.")
    parser.add_argument("--dedupe", action="store_true", help="Apply deduplication after consolidation.")
    parser.add_argument("--dedupe-keys", type=str, help="Comma-separated list of key columns for dedupe (overrides automatic selection).")
    parser.add_argument("--weekly", action="store_true", help="Consolidate only weekly player stats (pattern 'weekly_player_stats_') instead of mixing yearly + weekly.")
    parser.add_argument("--score-weekly", action="store_true", help="Shortcut: implies --weekly --score with union mode.")
    return parser.parse_args()


def prune_matched_parquets(consolidated: Path, pattern: str = "player_stats") -> int:
    """Delete parquet files in OUTPUT_SUBDIR that match pattern (excluding consolidated)."""
    deleted = 0
    for p in OUTPUT_SUBDIR.glob("*.parquet"):
        if p == consolidated:
            continue
        if pattern in p.name:
            try:
                p.unlink()
                deleted += 1
            except OSError as e:  # noqa: BLE001
                print(f"(warn) failed to delete {p.name}: {e}")
    if deleted:
        print(f"🧹 Pruned {deleted} parquet files matching '{pattern}'.")
    else:
        print("No parquet files pruned.")
    return deleted


def main():
    args = parse_args()

    performed_action = False

    if args.list:
        files = discover_raw_csvs()
        if not files:
            print("(no raw CSV files found in data/)")
            return
        print("Discovered raw CSV files:")
        for f in files:
            print(f" - {f}")
        performed_action = True

    if args.file:
        target = Path(args.file)
        if not target.exists():
            # Allow relative inside data/
            candidate = DATA_DIR / target
            if candidate.exists():
                target = candidate
            else:
                print(f"File not found: {args.file}")
                performed_action = True  # treat as handled
        if target.exists():
            out = OUTPUT_SUBDIR / (target.stem + ".parquet")
            roster_players = load_roster_players()
            clean_nfl_data(target, out, roster_players)
            performed_action = True
    if args.all:
        roster_players = load_roster_players()
        if roster_players:
            print(f"Loaded {len(roster_players)} roster player names for filtering.")
        outputs = batch_clean(roster_players)
        print(f"Finished batch. {len(outputs)} parquet files written to {OUTPUT_SUBDIR}/")
        performed_action = True

    # Derive implicit options
    if args.score_weekly:
        args.weekly = True
        args.score = True
        if not args.consolidation_mode:
            args.consolidation_mode = "union"  # type: ignore[attr-defined]

    def auto_dedupe_keys() -> list[str]:
        # Preference order depending on presence of week column
        base_week = ["player_id", "season", "week"]
        base_season = ["player_id", "season"]
        weekly_alt = ["player_name", "team", "season", "week"]
        season_alt = ["player_name", "team", "season"]
        # We'll select after reading a small sample later; for now return both; real filtering done inside consolidate
        return base_week + base_season + weekly_alt + season_alt

    dedupe_keys: list[str] | None = None
    if args.dedupe or args.dedupe_keys:
        if args.dedupe_keys:
            dedupe_keys = [k.strip() for k in args.dedupe_keys.split(",") if k.strip()]
        else:
            dedupe_keys = auto_dedupe_keys()

    pattern = "weekly_player_stats_" if args.weekly else "player_stats"

    if args.consolidate_output:
        consolidated = consolidate_player_stats(
            Path(args.consolidate_output),
            pattern=pattern,
            mode=args.consolidation_mode,
            dedupe_keys=dedupe_keys,
        )
        if args.prune_matched:
            prune_matched_parquets(consolidated)
        if args.score:
            apply_fantasy_scoring(consolidated)
        performed_action = True
    elif args.all and not args.no_auto_consolidate:
        # Auto consolidate to default path
        default_out = OUTPUT_SUBDIR / "all_player_stats.parquet"
        try:
            consolidated = consolidate_player_stats(
                default_out,
                pattern=pattern,
                mode=args.consolidation_mode,
                dedupe_keys=dedupe_keys,
            )
            if args.prune_matched:
                prune_matched_parquets(consolidated)
            if args.score:
                apply_fantasy_scoring(consolidated)
        except FileNotFoundError as e:  # no matching files; warn but continue
            print(f"(auto consolidate skipped: {e})")

    if not performed_action:
        print("No action specified. Use --list, --file, --all or --consolidate-output.")


if __name__ == "__main__":  # pragma: no cover
    main()

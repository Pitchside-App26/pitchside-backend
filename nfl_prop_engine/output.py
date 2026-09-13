"""Step 7: output -- a ranked markdown table (stdout/logs) plus a JSON export
consumed by the static site in site/ (published to GitHub Pages by the
weekly workflow). The markdown table came first per the spec, to prove the
ranking logic was defensible before building a UI on top of it; the JSON
export is that next step now that a real run has produced sane output.
"""
import json
from datetime import datetime, timezone

from config import STAT_LABELS
from rank_props import RankedProp

KNOWN_LIMITATIONS = """
Known limitations (see README for detail):
- Opponent-allowed stats are grouped by broad position (WR/TE pooled, etc),
  not fine-grained matchup data (slot/outside, man/zone).
- Name matching will have gaps, especially early on -- unmatched props are
  logged as warnings, not silently dropped.
- Rows marked "low" confidence rest on a historical-analogue prior (rookie)
  or a thin real sample, not a full blended veteran projection.
- Tackle props may show a systematic offset vs. the sportsbook's line if
  nflverse's tackle count disagrees with whatever source the book used --
  a known data-quality issue in the industry, not a bug here.
- This is a heuristic blend, not a backtested statistical model.
""".strip()


def _fmt(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def format_hit_rate(hit_rate: float | None, sample_size: int) -> str:
    if hit_rate is None:
        return "-"
    return f"{hit_rate:.0%} ({sample_size}g)"


def to_markdown_table(ranked: list[RankedProp]) -> str:
    header = "| Player | Stat | Line | Projection | Edge | Hit Rate | Confidence |"
    sep = "|---|---|---|---|---|---|---|"
    rows = [header, sep]
    for p in ranked:
        confidence_label = p.confidence if p.method == "veteran" else f"{p.confidence} ({p.method})"
        rows.append(
            f"| {p.player_name} | {p.stat_col} | {_fmt(p.line)} | {_fmt(p.projection)} "
            f"({p.direction}) | {p.edge_score:+.2f} | {format_hit_rate(p.hit_rate, p.sample_size)} "
            f"| {confidence_label} |"
        )
    return "\n".join(rows)


def print_report(ranked: list[RankedProp], season: int, week: int) -> None:
    print(f"# NFL Prop Rankings -- Season {season}, Week {week}\n")
    print(to_markdown_table(ranked))
    print()
    print(KNOWN_LIMITATIONS)


def to_json_records(ranked: list[RankedProp]) -> list[dict]:
    records = []
    for p in ranked:
        edge_pct = (p.projection - p.line) / p.line if p.line else None
        records.append({
            "player": p.player_name,
            "team": p.team,
            "opponent": p.opponent,
            "kickoff": p.kickoff,
            "stat": p.stat_col,
            "stat_label": STAT_LABELS.get(p.stat_col, p.stat_col),
            "line": p.line,
            "projection": round(p.projection, 1),
            "direction": p.direction,
            "edge_score": round(p.edge_score, 3),
            "edge_pct": round(edge_pct * 100, 1) if edge_pct is not None else None,
            "hit_rate": round(p.hit_rate, 3) if p.hit_rate is not None else None,
            "sample_size": p.sample_size,
            "confidence": p.confidence,
            "method": p.method,
        })
    return records


def write_json(ranked: list[RankedProp], season: int, week: int, path: str) -> None:
    payload = {
        "season": season,
        "week": week,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "props": to_json_records(ranked),
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)

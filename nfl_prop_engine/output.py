"""Step 7: v1 output -- a ranked markdown table, printed to stdout.

Not wired into any UI yet, per the spec: prove the ranking logic produces
something defensible before building on top of it. A JSON export is a
reasonable v2 once there's a few weeks of track record (see results_log.py
for the durable logging that track record depends on).
"""
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

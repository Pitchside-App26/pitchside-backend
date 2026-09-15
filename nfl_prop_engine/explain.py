"""Turns a Projection's internal numbers into a plain-English sentence or
two describing how the projection was actually reached. Built entirely
from real intermediate values the projection engine already computed --
nothing here is inferred or guessed after the fact from the final number.
"""
from projection_engine import Projection


def _fmt(v: float | None, digits: int = 1) -> str:
    return "-" if v is None else f"{v:.{digits}f}"


def explain_projection(proj: Projection) -> str:
    if proj.method == "rookie_prior":
        return _explain_rookie(proj)
    return _explain_veteran(proj)


def _explain_rookie(proj: Projection) -> str:
    slot = f"pick #{proj.analog_pick}" if proj.analog_pick else "similar undrafted rookies"
    n = proj.n_analog_players or 0
    parts = [
        f"No NFL games played yet, so this is a historical-analogue projection, not "
        f"a real track record: the median first-3-game production of {n} other "
        f"{proj.analog_position or 'players'} drafted near {slot} was {_fmt(proj.projection)}. "
        f"No opponent adjustment applied at this sample size -- treat as low confidence."
    ]
    parts.append(_game_context_sentence(proj))
    return " ".join(p for p in parts if p)


def _explain_veteran(proj: Projection) -> str:
    parts = []

    if proj.n_current_games == 0 and proj.prior_season_avg is not None:
        parts.append(
            f"No games played yet this season, so the baseline leans almost entirely on "
            f"last season's {proj.n_prior_games}-game average ({_fmt(proj.prior_season_avg)})."
        )
    elif proj.prior_season_avg is not None:
        weight_pct = round(proj.prior_weight * 100) if proj.prior_weight is not None else None
        reason = []
        if proj.n_current_games < 4:
            reason.append("thin current-season sample")
        if proj.team_changed:
            reason.append("a team change")
        reason_str = f" ({', '.join(reason)})" if reason else ""
        parts.append(
            f"Blends this season's {proj.n_current_games}-game average "
            f"({_fmt(proj.current_season_avg)}) with last season's {_fmt(proj.prior_season_avg)}, "
            f"weighting last season about {weight_pct}%{reason_str}."
        )
    else:
        parts.append(
            f"Based on this season's {proj.n_current_games}-game average of "
            f"{_fmt(proj.current_season_avg)} -- no prior-season data available for this player."
        )

    if proj.last5_avg is not None and proj.baseline is not None:
        parts.append(
            f"Averaged that against a recent-form figure of {_fmt(proj.last5_avg)} "
            f"to get a baseline of {_fmt(proj.baseline)}."
        )

    if proj.opp_factor is not None and proj.opponent_team:
        pct = (proj.opp_factor - 1) * 100
        if abs(pct) < 3:
            parts.append(f"{proj.opponent_team} grades out close to league-average here, so little adjustment applied.")
        else:
            direction = "tougher" if pct < 0 else "more favorable"
            parts.append(f"Adjusted {pct:+.0f}% for a {direction}-than-average matchup against {proj.opponent_team}.")

    context_sentence = _game_context_sentence(proj)
    if context_sentence:
        parts.append(context_sentence)

    if proj.method == "thin_sample":
        parts.append(
            "Flagged low confidence: very few combined games (current + prior season) "
            "behind this number."
        )

    return " ".join(parts)


def _game_context_sentence(proj: Projection) -> str:
    """Describes the spread/total adjustment, but only when it moved the
    number enough to matter -- same >=3% threshold explain.py already uses
    for the opponent adjustment, so a negligible tilt doesn't clutter every
    single prop's explanation with boilerplate."""
    if proj.game_context_pct is None or abs(proj.game_context_pct) < 3:
        return ""
    role = "favored by" if (proj.team_spread or 0) > 0 else "an underdog by"
    spread_note = f" (team {role} {abs(proj.team_spread):.1f})" if proj.team_spread is not None else ""
    return f"Adjusted {proj.game_context_pct:+.0f}% for this week's spread/total{spread_note}."

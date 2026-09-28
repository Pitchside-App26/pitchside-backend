"""GitHub side of bet-slip intake, run by .github/workflows/bet-slip.yml.

  python bet_slip_bot.py intake              # new bet-slip issue: read it, post a draft
  python bet_slip_bot.py comment             # Dan replied: confirm / cancel / retry / correction
  python bet_slip_bot.py reply --file F      # post F as a comment (after a successful save)

Reads GITHUB_TOKEN, GITHUB_REPOSITORY, GITHUB_REPOSITORY_OWNER, ISSUE_NUMBER
and (for "comment") COMMENT_ID from the environment. The comment text is
fetched from the API here rather than passed through the workflow file,
so nothing Dan (or anyone) types is ever interpolated into a shell command.
"""
import argparse
import logging
import os
import sqlite3
import sys

import requests

import bet_slips
from config import BET_SLIP, RESULTS_DB_PATH, get_current_nfl_season
from prop_bets_log import AlreadySettledError, replace_slips_for_issue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API = "https://api.github.com"


def _headers(accept: str = "application/vnd.github+json") -> dict:
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _repo_path(path: str) -> str:
    return f"{API}/repos/{os.environ['GITHUB_REPOSITORY']}{path}"


def get_issue(number: int) -> dict:
    # full+json includes body_html, where uploaded images appear as signed
    # URLs the runner can download.
    resp = requests.get(_repo_path(f"/issues/{number}"), headers=_headers("application/vnd.github.full+json"), timeout=30)
    resp.raise_for_status()
    return resp.json()


def list_comments(number: int) -> list[dict]:
    comments, page = [], 1
    while True:
        resp = requests.get(
            _repo_path(f"/issues/{number}/comments"), headers=_headers("application/vnd.github.full+json"),
            params={"per_page": 100, "page": page}, timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        comments += batch
        if len(batch) < 100:
            return comments
        page += 1


def get_comment(comment_id: int) -> dict:
    resp = requests.get(
        _repo_path(f"/issues/comments/{comment_id}"), headers=_headers("application/vnd.github.full+json"), timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def post_comment(number: int, body: str) -> None:
    resp = requests.post(_repo_path(f"/issues/{number}/comments"), headers=_headers(), json={"body": body}, timeout=30)
    resp.raise_for_status()


def close_issue(number: int, reason: str) -> None:
    resp = requests.patch(
        _repo_path(f"/issues/{number}"), headers=_headers(),
        json={"state": "closed", "state_reason": reason}, timeout=30,
    )
    resp.raise_for_status()


def ensure_label(number: int, labels: list[dict]) -> None:
    if any(label["name"] == BET_SLIP["label"] for label in labels):
        return
    resp = requests.post(
        _repo_path(f"/issues/{number}/labels"), headers=_headers(), json={"labels": [BET_SLIP["label"]]}, timeout=30,
    )
    resp.raise_for_status()


def download_images(urls: list[str]) -> tuple[list[tuple[str, bytes]], list[str]]:
    """No Authorization header: these are pre-signed storage URLs, and the
    GitHub token must never be sent to a host outside api.github.com."""
    images, problems = [], []
    for n, url in enumerate(urls[: BET_SLIP["max_images"]], start=1):
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            problems.append(f"Image {n} couldn't be downloaded (HTTP {resp.status_code}).")
            continue
        data = resp.content
        media_type = bet_slips.detect_media_type(data)
        if media_type == "heic":
            problems.append(f"Image {n} is a HEIC photo, which can't be read. Attach a screenshot (PNG) instead.")
        elif media_type is None:
            problems.append(f"Image {n} isn't a PNG, JPEG, GIF or WebP file.")
        elif len(data) > BET_SLIP["max_image_bytes"]:
            problems.append(f"Image {n} is over 5 MB. Attach a smaller screenshot.")
        else:
            images.append((media_type, data))
    if len(urls) > BET_SLIP["max_images"]:
        problems.append(f"Only the first {BET_SLIP['max_images']} images were read.")
    return images, problems


def current_week() -> int | None:
    try:
        from fetch_schedule import fetch_week_games

        games = fetch_week_games(get_current_nfl_season())
        return None if games.empty else int(games["week"].iloc[0])
    except Exception:
        logger.exception("Couldn't load the schedule to work out the week")
        return None


def roster_names() -> list[str] | None:
    try:
        import nfl_data_py as nfl

        roster = nfl.import_seasonal_rosters([get_current_nfl_season()])
        return sorted(set(roster["player_name"].dropna()))
    except Exception:
        logger.exception("Couldn't load the roster; player names will be kept as written on the slip")
        return None


def slip_image_urls(issue: dict, comments: list[dict]) -> list[str]:
    """Screenshots from the issue itself and from the owner's comments, in
    order: on a phone it's as natural to add the screenshot in a follow-up
    comment as in the issue. Other people's images are never read."""
    owner = os.environ["GITHUB_REPOSITORY_OWNER"]
    urls = bet_slips.extract_image_urls(issue.get("body_html"))
    for comment in comments:
        if (comment.get("user") or {}).get("login") == owner:
            urls += bet_slips.extract_image_urls(comment.get("body_html"))
    return list(dict.fromkeys(urls))


def read_slip(number: int, previous: dict | None, correction: str | None) -> str:
    """Reads the issue's screenshots and returns the comment to post: a
    draft, or a plain explanation of why there isn't one."""
    issue = get_issue(number)
    urls = slip_image_urls(issue, list_comments(number))
    if not urls:
        return bet_slips.status_comment(
            "I couldn't find a screenshot on this issue. Add one (edit the issue or post it as a comment)."
        )

    images, problems = download_images(urls)
    if not images:
        return bet_slips.status_comment(
            "I couldn't read any of the attached images:\n" + "\n".join(f"- {p}" for p in problems)
            + "\n\nFix the attachment, then reply **retry**."
        )

    try:
        parsed = bet_slips.parse_slip_images(
            images, previous=previous, correction=correction, notes=bet_slips.strip_images(issue.get("body")),
        )
    except bet_slips.SlipParseError as exc:
        logger.exception("Slip parse failed")
        return bet_slips.status_comment(f"Reading the slip failed ({exc}). Nothing was logged. Reply **retry** to try again.")

    week = previous["week"] if previous and previous.get("week") is not None else current_week()
    draft = bet_slips.normalize(parsed, week, roster_names())
    draft["warnings"] = problems + draft["warnings"]
    return bet_slips.render_draft_comment(draft)


def _already_logged(number: int) -> bool:
    conn = sqlite3.connect(RESULTS_DB_PATH)
    try:
        return conn.execute("SELECT 1 FROM bet_slips WHERE source_issue=?", (number,)).fetchone() is not None
    except sqlite3.OperationalError:
        return False  # bet_slips table not created yet: nothing has ever been logged
    finally:
        conn.close()


def _set_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.write(f"{name}={value}\n")


def cmd_intake(number: int) -> None:
    issue = get_issue(number)
    comments = list_comments(number)
    if bet_slips.already_handled(comments):
        logger.info("Issue #%s already has a bet-slip reply; skipping duplicate trigger.", number)
        return
    ensure_label(number, issue.get("labels", []))
    post_comment(number, read_slip(number, previous=None, correction=None))


def cmd_comment(number: int, comment_id: int, reply_file: str) -> None:
    comment = get_comment(comment_id)
    # Checked here as well as in the workflow's `if:`, so this script can't
    # be pointed at someone else's comment by mistake.
    if (comment.get("user") or {}).get("login") != os.environ["GITHUB_REPOSITORY_OWNER"]:
        logger.info("Comment %s isn't from the repo owner; ignoring.", comment_id)
        return

    command = bet_slips.reply_command(comment)
    text = bet_slips.strip_images(comment.get("body"))
    comments = list_comments(number)
    draft = bet_slips.latest_draft(comments)

    if command == "cancel":
        if _already_logged(number):
            post_comment(number, bet_slips.status_comment(
                "This slip is already logged, so nothing was removed. Reply with a correction if it's wrong."
            ))
        else:
            post_comment(number, bet_slips.status_comment("Discarded. Nothing was logged."))
            close_issue(number, "not_planned")
        return

    if command == "retry":
        post_comment(number, read_slip(number, previous=None, correction=None))
        return

    if command == "correction":
        post_comment(number, read_slip(number, previous=draft, correction=text))
        return

    # confirm
    if draft is None:
        post_comment(number, bet_slips.status_comment(
            "There's no draft to confirm yet. Wait for my reading of the slip, or reply **retry**."
        ))
        return
    if not draft["slips"]:
        post_comment(number, bet_slips.status_comment("The last reading found no bets, so there's nothing to log."))
        return
    if draft["week"] is None:
        post_comment(number, bet_slips.status_comment("I need the NFL week before logging. Reply e.g. `week is 4`."))
        return
    if bet_slips.unprocessed_change_before(comments, os.environ["GITHUB_REPOSITORY_OWNER"], comment_id):
        post_comment(number, bet_slips.status_comment(
            "You sent a change after my last reading that I haven't processed (it may have been skipped). "
            "Nothing was logged. Send the change again, check the new reading, then confirm."
        ))
        return

    try:
        n_slips, n_legs = replace_slips_for_issue(number, draft["week"], draft["slips"])
    except AlreadySettledError:
        post_comment(number, bet_slips.status_comment(
            "These bets have already been settled, so the logged version can't be changed."
        ))
        return

    with open(reply_file, "w") as f:
        f.write(bet_slips.status_comment(
            f"Logged {n_slips} bet{'s' if n_slips != 1 else ''} ({n_legs} leg{'s' if n_legs != 1 else ''}) "
            f"to Week {draft['week']}. If something's wrong, reply with a correction and confirm again; "
            "it replaces what was logged."
        ))
    _set_output("logged", "true")


def cmd_reply(number: int, reply_file: str, close: bool) -> None:
    with open(reply_file) as f:
        post_comment(number, f.read())
    if close:
        close_issue(number, "completed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["intake", "comment", "reply"])
    parser.add_argument("--file", help="reply file (comment writes it, reply posts it)")
    parser.add_argument("--close", action="store_true", help="close the issue after replying")
    args = parser.parse_args()

    number = int(os.environ["ISSUE_NUMBER"])
    if args.command == "intake":
        cmd_intake(number)
    elif args.command == "comment":
        cmd_comment(number, int(os.environ["COMMENT_ID"]), args.file)
    else:
        cmd_reply(number, args.file, args.close)


if __name__ == "__main__":
    sys.exit(main())

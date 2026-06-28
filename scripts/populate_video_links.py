"""
One-off script to enrich the abbreviations table with YouTube tutorial links.

Usage:
    docker compose exec -e YOUTUBE_API_KEY=<key> backend python scripts/populate_video_links.py

Requirements:
    - YOUTUBE_API_KEY must be set in .env (YouTube Data API v3 key).
    - The abbreviations table must already be populated (run seed_abbreviations.py first).

Behaviour:
    - Reads abbreviations that are eligible (type in STITCH, DECREASE, INCREASE, TECHNIQUE,
      CONSTRUCTION) and still have no video_link in the DB — so the script is safely resumable
      after interruption (e.g. by hitting the daily quota of 10,000 units / 100 calls).
    - Fetches the top YouTube search result for each abbreviation and writes the embed URL
      into the CSV file (saving after each match), keeping the CSV as the source of truth.
    - At the end — both on normal completion and on quota exceeded — calls the seeder with
      update_existing=True to push the CSV values into the database.
    - Stops gracefully on a quota-exceeded 403 and prints a summary.
"""

import csv
import sys
from pathlib import Path

import requests

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import pattern, scaling, user, yarn  # noqa: F401
from app.models.abbreviation import Abbreviation, AbbreviationType
from scripts.seed_abbreviations import CSV_PATH, seed_abbreviations

ELIGIBLE_TYPES = {
    AbbreviationType.STITCH,
    AbbreviationType.DECREASE,
    AbbreviationType.INCREASE,
    AbbreviationType.TECHNIQUE,
    AbbreviationType.CONSTRUCTION,
}

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


class QuotaExceededError(Exception):
    pass


def fetch_video_id(abbreviation: Abbreviation) -> str | None:
    query = (
        f"{abbreviation.full_name} {abbreviation.type.value} "
        f"{abbreviation.craft.value} tutorial for beginners"
    )
    response = requests.get(
        YOUTUBE_SEARCH_URL,
        params={
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 1,
            "key": settings.YOUTUBE_API_KEY,
        },
        timeout=10,
    )

    if response.status_code == 403:
        data = response.json()
        errors = data.get("error", {}).get("errors", [])
        if any(e.get("reason") == "quotaExceeded" for e in errors):
            raise QuotaExceededError()

    response.raise_for_status()

    items = response.json().get("items", [])
    if not items:
        return None

    return items[0]["id"]["videoId"]


def _load_csv() -> tuple[list[dict], list[str]]:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "video_link" not in fieldnames:
        fieldnames.append("video_link")
        for row in rows:
            row["video_link"] = ""

    return rows, fieldnames


def _save_csv(rows: list[dict], fieldnames: list[str]) -> None:
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def populate_video_links() -> None:
    rows, fieldnames = _load_csv()
    csv_index = {(row["abbreviation"], row["craft"]): row for row in rows}

    db = SessionLocal()
    try:
        eligible = (
            db.query(Abbreviation)
            .filter(
                Abbreviation.type.in_(ELIGIBLE_TYPES),
                Abbreviation.video_link.is_(None),
            )
            .all()
        )
    finally:
        db.close()

    total = len(eligible)
    print(f"Found {total} abbreviation(s) to process.\n")

    processed = 0
    found = 0

    for abbr in eligible:
        print(
            f"[{processed + 1}/{total}] {abbr.abbreviation} ({abbr.full_name}) ...",
            end=" ",
        )

        try:
            video_id = fetch_video_id(abbr)
        except QuotaExceededError:
            remaining = total - processed
            print(
                f"\nYouTube API quota exceeded.\n"
                f"Processed: {processed} | Found: {found} | Remaining: {remaining}\n"
                f"Re-run the script tomorrow to continue from where it left off."
            )
            seed_abbreviations(update_existing=True)
            return
        except requests.RequestException as exc:
            print(f"HTTP error: {exc} — skipping.")
            processed += 1
            continue

        if video_id:
            video_url = f"https://www.youtube.com/embed/{video_id}"
            csv_row = csv_index.get((abbr.abbreviation, abbr.craft.value))
            if csv_row is not None:
                csv_row["video_link"] = video_url
                _save_csv(rows, fieldnames)
            found += 1
            print(f"found ({video_id})")
        else:
            print("no results, skipped.")

        processed += 1

    remaining = total - processed
    print(
        f"\nDone. Processed: {processed} | Found: {found} | "
        f"Skipped (no results): {processed - found} | Remaining: {remaining}"
    )
    seed_abbreviations(update_existing=True)


if __name__ == "__main__":
    populate_video_links()

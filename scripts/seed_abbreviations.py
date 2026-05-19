import csv
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.abbreviation import Abbreviation, AbbreviationCraft, AbbreviationType

CSV_PATH = Path(__file__).resolve().parent / "data" / "abbreviations_seed.csv"


def seed_abbreviations():
    db = SessionLocal()
    try:
        existing = db.query(Abbreviation).count()
        if existing > 0:
            print(
                f"Table 'abbreviations' already has {existing} entries. Skipping seed."
            )
            return

        rows = []
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(
                    Abbreviation(
                        abbreviation=row["abbreviation"],
                        full_name=row["full_name"],
                        description=row["description"] or None,
                        type=AbbreviationType(row["type"]),
                        craft=AbbreviationCraft(row["craft"]),
                        video_link=row["video_link"] or None,
                    )
                )

        db.add_all(rows)
        db.commit()

        knitting = sum(1 for r in rows if r.craft == AbbreviationCraft.KNITTING)
        crochet = sum(1 for r in rows if r.craft == AbbreviationCraft.CROCHET)
        print(
            f"Inserted {len(rows)} abbreviations: {knitting} KNITTING, {crochet} CROCHET."
        )

    except Exception as e:
        db.rollback()
        print(f"Error during seed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed_abbreviations()

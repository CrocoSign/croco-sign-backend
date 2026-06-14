"""Stream pjm-segments from HuggingFace and insert into the segment table.

Requires an existing SQLite DB produced by csv_to_sqlite.py (video_metadata
table must be populated first).

Usage:
    uv run python scripts/hf_segments_to_sqlite.py data/pjm.db
"""

import argparse
import sqlite3
from pathlib import Path

from datasets import Value, load_dataset

REPO_ID = "croco-corp/pjm-segments"

SIDE_MAP = {"M": "-", "L": "left", "R": "right"}

DDL = """
CREATE TABLE IF NOT EXISTS segment (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id        TEXT    NOT NULL UNIQUE,
    sentence          TEXT    NOT NULL,
    video_metadata_id INTEGER NOT NULL REFERENCES video_metadata(id)
);

CREATE INDEX IF NOT EXISTS idx_segment_video_metadata ON segment(video_metadata_id);
"""


def build_lookup(con: sqlite3.Connection) -> dict[tuple[int, str], int]:
    """Return {(video_id, speaker_side): video_metadata.id} for FK resolution."""
    rows = con.execute("SELECT id, video_id, speaker_side FROM video_metadata").fetchall()
    return {(video_id, speaker_side): pk for pk, video_id, speaker_side in rows}


def parse_key(key: str) -> tuple[int, str] | None:
    """Parse __key__ like '004_000_M' into (video_id, speaker_side) or None."""
    parts = key.split("_")
    if len(parts) < 3:
        return None
    video_id = int(parts[0])
    side_code = parts[-1]
    speaker_side = SIDE_MAP.get(side_code)
    if speaker_side is None:
        return None
    return video_id, speaker_side


def load_existing_ids(con: sqlite3.Connection) -> set[str]:
    """Return the set of segment_ids already present in the DB."""
    rows = con.execute("SELECT segment_id FROM segment").fetchall()
    return {row[0] for row in rows}


def load_segments(db_path: Path) -> None:
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(DDL)

    lookup = build_lookup(con)
    print(f"Loaded {len(lookup)} video_metadata entries for FK resolution.")

    existing_ids = load_existing_ids(con)

    ds = load_dataset(REPO_ID, split="train", streaming=True)
    # cast mp4 column to skip video decoding — we only need __key__ and txt
    ds = ds.cast_column("mp4", Value("binary"))
    print(f"Skipping {len(existing_ids)} segment IDs already in DB.")
    ds = ds.filter(lambda record: record["__key__"] not in existing_ids)

    inserted = skipped = 0
    print("Starting interation")
    with con:
        for record in ds:
            key = record["__key__"]
            sentence = record["txt"]

            parsed = parse_key(key)
            if parsed is None:
                print(f"  WARN: cannot parse key '{key}', skipping.")
                skipped += 1
                continue

            video_metadata_id = lookup.get(parsed)
            if video_metadata_id is None:
                print(f"  WARN: no video_metadata match for key '{key}' → {parsed}, skipping.")
                skipped += 1
                continue

            con.execute(
                "INSERT OR IGNORE INTO segment (segment_id, sentence, video_metadata_id) VALUES (?, ?, ?)",
                (key, sentence, video_metadata_id),
            )
            inserted += 1
            if inserted % 1000 == 0:
                print(f"processed:{inserted}")
    count = con.execute("SELECT COUNT(*) FROM segment").fetchone()[0]
    con.close()

    print(f"\nDone. {inserted} inserted, {skipped} skipped → {count} total segments in DB.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import HF pjm-segments into SQLite")
    parser.add_argument("db", type=Path)
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"DB not found: {args.db} — run csv_to_sqlite.py first.")

    load_segments(args.db)


if __name__ == "__main__":
    main()

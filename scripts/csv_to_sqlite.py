"""Convert pjm_data CSV to SQLite with Signer and VideoMetadata tables.

Usage:
    python scripts/csv_to_sqlite.py data/pjm_data_23-03-2026.csv data/pjm.db
"""

import argparse
import csv
import sqlite3
from pathlib import Path


DDL = """
CREATE TABLE IF NOT EXISTS signer (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    speaker_id  TEXT    NOT NULL UNIQUE,
    sex         TEXT    NOT NULL,
    age         TEXT    NOT NULL,
    special_case TEXT   NOT NULL
);

CREATE TABLE IF NOT EXISTS video_metadata (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id        INTEGER NOT NULL UNIQUE,
    video_url       TEXT    NOT NULL,
    subtitles_url   TEXT    NOT NULL,
    video_type      TEXT    NOT NULL,
    task_id         INTEGER NOT NULL,
    speaker_side    TEXT    NOT NULL,
    signer_id       INTEGER NOT NULL REFERENCES signer(id)
);

CREATE INDEX IF NOT EXISTS idx_video_metadata_signer ON video_metadata(signer_id);
"""


def convert(csv_path: Path, db_path: Path) -> None:
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(DDL)

    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    signer_map: dict[str, int] = {}

    with con:
        for row in rows:
            speaker_id = row["speaker_id"]
            if speaker_id not in signer_map:
                cur = con.execute(
                    "INSERT OR IGNORE INTO signer (speaker_id, sex, age, special_case) VALUES (?, ?, ?, ?)",
                    (speaker_id, row["sex"], row["age"], row["special_case"]),
                )
                if cur.lastrowid:
                    signer_map[speaker_id] = cur.lastrowid
                else:
                    (signer_id,) = con.execute(
                        "SELECT id FROM signer WHERE speaker_id = ?", (speaker_id,)
                    ).fetchone()
                    signer_map[speaker_id] = signer_id

            con.execute(
                """INSERT OR IGNORE INTO video_metadata
                   (video_id, video_url, subtitles_url, video_type, task_id, speaker_side, signer_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    int(row["video_id"]),
                    row["video_url"],
                    row["subtitles_url"],
                    row["video_type"],
                    int(row["task_id"]),
                    row["speaker_side"],
                    signer_map[speaker_id],
                ),
            )

    signer_count = con.execute("SELECT COUNT(*) FROM signer").fetchone()[0]
    video_count = con.execute("SELECT COUNT(*) FROM video_metadata").fetchone()[0]
    con.close()

    print(f"Done. {signer_count} signers, {video_count} video entries → {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert PJM CSV to SQLite")
    parser.add_argument("csv", type=Path)
    parser.add_argument("db", type=Path)
    args = parser.parse_args()

    if not args.csv.exists():
        raise SystemExit(f"CSV not found: {args.csv}")

    args.db.parent.mkdir(parents=True, exist_ok=True)
    convert(args.csv, args.db)


if __name__ == "__main__":
    main()

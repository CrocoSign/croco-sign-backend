"""Parse the metrics markdown table and load it into SQLite.

Builds four tables describing translation experiments and their scores:
`model`, `metric_definition`, `experiment`, and the `experiments_metrics`
junction. Re-runnable: tables are created if missing and rows are upserted, so
running twice does not duplicate data.

Usage:
    python scripts/metrics_to_sqlite.py metrics.md data/pjm.db
"""

import argparse
import sqlite3
from pathlib import Path

DDL = """
CREATE TABLE IF NOT EXISTS model (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name    TEXT    NOT NULL UNIQUE,
    architecture_fig TEXT   NOT NULL
);

CREATE TABLE IF NOT EXISTS metric_definition (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transfer_source TEXT   NOT NULL,
    split           TEXT   NOT NULL,
    model_id        INTEGER NOT NULL REFERENCES model(id),
    UNIQUE (model_id, transfer_source, split)
);

CREATE TABLE IF NOT EXISTS experiments_metrics (
    experiment_id INTEGER NOT NULL REFERENCES experiment(id),
    metric_id     INTEGER NOT NULL REFERENCES metric_definition(id),
    value         REAL    NOT NULL,
    PRIMARY KEY (experiment_id, metric_id)
);

CREATE INDEX IF NOT EXISTS idx_experiment_model ON experiment(model_id);
"""

# Model display name (as it appears in the markdown) -> architecture figure path.
ARCHITECTURE_FIG = {
    "SpaMo": "resources/fig-spamo.png",
    "SpaMo (modyf.)": "resources/fig-spamo-mod.png",
    "Uni-Sign": "resources/fig-unisign.png",
}

# Metric name -> human-readable description (Polish, matching the dataset).
METRIC_DESCRIPTIONS = {
    "BLEU-1": "Precyzja unigramowa tłumaczenia względem referencji (BLEU dla n=1).",
    "BLEU-2": "Precyzja bigramowa tłumaczenia względem referencji (BLEU dla n=2).",
    "BLEU-3": "Precyzja trigramowa tłumaczenia względem referencji (BLEU dla n=3).",
    "BLEU-4": "Precyzja czterogramowa tłumaczenia względem referencji (BLEU dla n=4).",
    "ROUGE-L": "Miara F oparta na najdłuższym wspólnym podciągu (LCS) hipotezy i referencji.",
    "BLEURT": "Wyuczona metryka jakości tłumaczenia oparta na modelu BERT.",
    "chrF": "Miara F oparta na n-gramach znakowych (character n-gram F-score).",
    "BERTScore": "Podobieństwo semantyczne liczone na osadzeniach kontekstowych BERT.",
}

# Non-metric leading columns in the table.
META_COLUMNS = {"Model", "Źródło transferu", "Split"}


def parse_markdown_table(md_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (metric_column_names, rows) parsed from a GitHub-style md table."""
    lines = [
        line.strip()
        for line in md_path.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("|")
    ]
    if len(lines) < 2:
        raise SystemExit(f"No markdown table found in {md_path}")

    def cells(line: str) -> list[str]:
        # Drop the empty fields produced by the leading/trailing pipes.
        return [c.strip() for c in line.split("|")[1:-1]]

    header = cells(lines[0])
    # lines[1] is the |---|---| separator row.
    data_lines = lines[2:]

    metric_columns = [
        col for col in header if col and col not in META_COLUMNS
    ]

    rows: list[dict[str, str]] = []
    for line in data_lines:
        values = cells(line)
        record = dict(zip(header, values))
        if not record.get("Model"):
            continue
        rows.append(record)
    return metric_columns, rows


def upsert_model(con: sqlite3.Connection, display_name: str) -> int:
    fig = ARCHITECTURE_FIG.get(display_name)
    if fig is None:
        raise SystemExit(f"No architecture figure mapping for model '{display_name}'")
    con.execute(
        "INSERT OR IGNORE INTO model (display_name, architecture_fig) VALUES (?, ?)",
        (display_name, fig),
    )
    (model_id,) = con.execute(
        "SELECT id FROM model WHERE display_name = ?", (display_name,)
    ).fetchone()
    return model_id


def upsert_metric(con: sqlite3.Connection, name: str) -> int:
    description = METRIC_DESCRIPTIONS.get(name, "")
    con.execute(
        "INSERT OR IGNORE INTO metric_definition (name, description) VALUES (?, ?)",
        (name, description),
    )
    (metric_id,) = con.execute(
        "SELECT id FROM metric_definition WHERE name = ?", (name,)
    ).fetchone()
    return metric_id


def upsert_experiment(
    con: sqlite3.Connection, model_id: int, transfer_source: str, split: str
) -> int:
    con.execute(
        """INSERT OR IGNORE INTO experiment (transfer_source, split, model_id)
           VALUES (?, ?, ?)""",
        (transfer_source, split, model_id),
    )
    (experiment_id,) = con.execute(
        """SELECT id FROM experiment
           WHERE model_id = ? AND transfer_source = ? AND split = ?""",
        (model_id, transfer_source, split),
    ).fetchone()
    return experiment_id


def load(md_path: Path, db_path: Path) -> None:
    metric_columns, rows = parse_markdown_table(md_path)

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(DDL)

    with con:
        metric_ids = {name: upsert_metric(con, name) for name in metric_columns}

        for row in rows:
            model_id = upsert_model(con, row["Model"])
            experiment_id = upsert_experiment(
                con, model_id, row["Źródło transferu"], row["Split"]
            )
            for metric_name in metric_columns:
                raw = row.get(metric_name, "")
                if raw == "":
                    continue
                con.execute(
                    """INSERT INTO experiments_metrics (experiment_id, metric_id, value)
                       VALUES (?, ?, ?)
                       ON CONFLICT (experiment_id, metric_id)
                       DO UPDATE SET value = excluded.value""",
                    (experiment_id, metric_ids[metric_name], float(raw)),
                )

    counts = {
        table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("model", "metric_definition", "experiment", "experiments_metrics")
    }
    con.close()
    print(
        "Done. "
        f"{counts['model']} models, "
        f"{counts['metric_definition']} metrics, "
        f"{counts['experiment']} experiments, "
        f"{counts['experiments_metrics']} scores → {db_path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Load metrics markdown into SQLite")
    parser.add_argument("markdown", type=Path)
    parser.add_argument("db", type=Path)
    args = parser.parse_args()

    if not args.markdown.exists():
        raise SystemExit(f"Markdown not found: {args.markdown}")

    args.db.parent.mkdir(parents=True, exist_ok=True)
    load(args.markdown, args.db)


if __name__ == "__main__":
    main()

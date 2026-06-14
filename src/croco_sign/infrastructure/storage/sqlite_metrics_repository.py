"""SQLite-backed MetricsRepository.

Reads the read-only benchmark catalog built by `scripts/metrics_to_sqlite.py`
(tables `model`, `metric_definition`, `experiment`, `experiments_metrics`). Same
approach as `SqliteSegmentRepository`: tiny indexed lookups over a local file,
run off the event loop with `asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import sqlite3

from croco_sign.domain.exceptions import ExperimentNotFoundError
from croco_sign.domain.models import (
    BenchmarkModel,
    Experiment,
    ExperimentRow,
    ExperimentScore,
    MetricDefinition,
    MetricsTable,
)

_METRICS_SQL = "SELECT id, name, description FROM metric_definition ORDER BY id"

# Experiments with their model, ordered for a stable matrix (by model then setup).
_EXPERIMENTS_SQL = """
SELECT
    e.id            AS experiment_id,
    e.transfer_source AS transfer_source,
    e.split         AS split,
    m.id            AS model_id,
    m.display_name  AS display_name,
    m.architecture_fig AS architecture_fig
FROM experiment e
JOIN model m ON m.id = e.model_id
ORDER BY m.id, e.id
"""

# Every (experiment, metric) score, joined to the metric name for keying.
_SCORES_SQL = """
SELECT
    em.experiment_id AS experiment_id,
    md.name          AS metric_name,
    em.value         AS value
FROM experiments_metrics em
JOIN metric_definition md ON md.id = em.metric_id
"""

_DETAIL_SQL = """
SELECT
    e.id            AS experiment_id,
    e.transfer_source AS transfer_source,
    e.split         AS split,
    m.id            AS model_id,
    m.display_name  AS display_name,
    m.architecture_fig AS architecture_fig
FROM experiment e
JOIN model m ON m.id = e.model_id
WHERE e.id = ?
"""

# An experiment's scores, ordered like the metric columns (by metric id).
_DETAIL_SCORES_SQL = """
SELECT
    md.id          AS metric_id,
    md.name        AS metric_name,
    md.description AS metric_description,
    em.value       AS value
FROM experiments_metrics em
JOIN metric_definition md ON md.id = em.metric_id
WHERE em.experiment_id = ?
ORDER BY md.id
"""


class SqliteMetricsRepository:
    """Implements the MetricsRepository port over a local SQLite file."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def list_metrics_table(self) -> MetricsTable:
        return await asyncio.to_thread(self._list_metrics_table_sync)

    async def get_experiment(self, id: int) -> Experiment:
        return await asyncio.to_thread(self._get_experiment_sync, id)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path, check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con

    def _list_metrics_table_sync(self) -> MetricsTable:
        con = self._connect()
        try:
            metric_rows = con.execute(_METRICS_SQL).fetchall()
            experiment_rows = con.execute(_EXPERIMENTS_SQL).fetchall()
            score_rows = con.execute(_SCORES_SQL).fetchall()
        finally:
            con.close()

        metrics = [
            MetricDefinition(id=r["id"], name=r["name"], description=r["description"])
            for r in metric_rows
        ]

        scores_by_experiment: dict[int, dict[str, float]] = {}
        for r in score_rows:
            scores_by_experiment.setdefault(r["experiment_id"], {})[r["metric_name"]] = (
                r["value"]
            )

        experiments = [
            ExperimentRow(
                id=r["experiment_id"],
                model=BenchmarkModel(
                    id=r["model_id"],
                    display_name=r["display_name"],
                    architecture_fig=r["architecture_fig"],
                ),
                transfer_source=r["transfer_source"],
                split=r["split"],
                scores=scores_by_experiment.get(r["experiment_id"], {}),
            )
            for r in experiment_rows
        ]
        return MetricsTable(metrics=metrics, experiments=experiments)

    def _get_experiment_sync(self, id: int) -> Experiment:
        con = self._connect()
        try:
            row = con.execute(_DETAIL_SQL, (id,)).fetchone()
            if row is None:
                raise ExperimentNotFoundError(f"Experiment {id} not found.")
            score_rows = con.execute(_DETAIL_SCORES_SQL, (id,)).fetchall()
        finally:
            con.close()

        model = BenchmarkModel(
            id=row["model_id"],
            display_name=row["display_name"],
            architecture_fig=row["architecture_fig"],
        )
        scores = [
            ExperimentScore(
                metric=MetricDefinition(
                    id=r["metric_id"],
                    name=r["metric_name"],
                    description=r["metric_description"],
                ),
                value=r["value"],
            )
            for r in score_rows
        ]
        return Experiment(
            id=row["experiment_id"],
            transfer_source=row["transfer_source"],
            split=row["split"],
            model=model,
            scores=scores,
        )

"""Application service for the benchmark metrics catalog and model diagrams."""

from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path

from croco_sign.domain.exceptions import ExperimentNotFoundError
from croco_sign.domain.models import Experiment, MetricsTable
from croco_sign.domain.ports import MetricsRepository


class MetricsService:
    """Orchestrates the metrics catalog (SQLite) and architecture diagram files.

    `resources_base_dir` is the root the figure paths stored in the DB are
    resolved against (the DB stores e.g. "resources/fig-spamo.png").
    """

    def __init__(
        self, repository: MetricsRepository, resources_base_dir: str
    ) -> None:
        self._repository = repository
        self._resources_base_dir = Path(resources_base_dir).resolve()

    async def list_metrics_table(self) -> MetricsTable:
        return await self._repository.list_metrics_table()

    async def get_experiment(self, id: int) -> Experiment:
        return await self._repository.get_experiment(id)

    async def get_architecture_image(self, experiment_id: int) -> tuple[bytes, str]:
        """Return (bytes, media_type) for the experiment's model diagram.

        Resolves the experiment first so a bad id is a clean 404 before touching
        the filesystem, mirroring SegmentService.get_segment_video.
        """
        experiment = await self._repository.get_experiment(experiment_id)
        path = self._resolve_figure(experiment.model.architecture_fig)
        data = await asyncio.to_thread(path.read_bytes)
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return data, media_type

    def _resolve_figure(self, fig: str) -> Path:
        """Resolve a DB-stored figure path under the resources base, guarding traversal."""
        path = (self._resources_base_dir / fig).resolve()
        # Defense-in-depth: the path is DB-trusted, but never serve outside the base.
        if not path.is_relative_to(self._resources_base_dir) or not path.is_file():
            raise ExperimentNotFoundError(
                f"Architecture figure '{fig}' is unavailable."
            )
        return path

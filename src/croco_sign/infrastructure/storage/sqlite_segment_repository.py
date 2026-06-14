"""SQLite-backed SegmentRepository.

Reads the local read-only catalog built by `scripts/csv_to_sqlite.py` and
`scripts/hf_segments_to_sqlite.py`. Queries are tiny indexed lookups against a
local file, so we use the stdlib `sqlite3` and offload the blocking calls to a
worker thread via `asyncio.to_thread` — the same pattern the service layer uses
for blocking translator work, and avoiding an extra async-driver dependency.
"""

from __future__ import annotations

import asyncio
import sqlite3

from croco_sign.domain.exceptions import SegmentNotFoundError
from croco_sign.domain.models import (
    Segment,
    SegmentFacets,
    SegmentFilters,
    SegmentPage,
    SegmentSummary,
    Signer,
    VideoMetadata,
)

# Shared FROM clause for both the list page and its (filtered) count, so the two
# always see the same rows. The `signer` join is always present because filters
# and the projection both reach into it.
_FROM = """
FROM segment s
JOIN video_metadata vm ON vm.id = s.video_metadata_id
JOIN signer sg         ON sg.id = vm.signer_id
"""

_LIST_SELECT = "SELECT s.id, s.segment_id, s.sentence, sg.age, sg.sex, sg.speaker_id"

_FACETS_SQL = {
    "ages": f"SELECT DISTINCT sg.age {_FROM} ORDER BY sg.age",
    "sexes": f"SELECT DISTINCT sg.sex {_FROM} ORDER BY sg.sex",
    "speaker_ids": f"SELECT DISTINCT sg.speaker_id {_FROM} ORDER BY sg.speaker_id",
}


def _where(filters: SegmentFilters) -> tuple[str, list[object]]:
    """Build a WHERE fragment (incl. leading 'WHERE' or empty) and its params."""
    clauses: list[str] = []
    params: list[object] = []
    # Multi-select fields: a non-empty tuple matches any of its values.
    for column, values in (
        ("sg.age", filters.ages),
        ("sg.sex", filters.sexes),
        ("sg.speaker_id", filters.speaker_ids),
    ):
        if values:
            placeholders = ", ".join("?" * len(values))
            clauses.append(f"{column} IN ({placeholders})")
            params.extend(values)
    if filters.sentence is not None:
        clauses.append("s.sentence LIKE ? COLLATE NOCASE")
        params.append(f"%{filters.sentence}%")
    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params


_DETAIL_SQL = """
SELECT
    s.id            AS segment_pk,
    s.segment_id    AS segment_id,
    s.sentence      AS sentence,
    vm.id           AS vm_id,
    vm.video_id     AS video_id,
    vm.video_url    AS video_url,
    vm.subtitles_url AS subtitles_url,
    vm.video_type   AS video_type,
    vm.task_id      AS task_id,
    vm.speaker_side AS speaker_side,
    sg.id           AS signer_id,
    sg.speaker_id   AS speaker_id,
    sg.sex          AS sex,
    sg.age          AS age,
    sg.special_case AS special_case
FROM segment s
JOIN video_metadata vm ON vm.id = s.video_metadata_id
JOIN signer sg         ON sg.id = vm.signer_id
WHERE s.id = ?
"""


class SqliteSegmentRepository:
    """Implements the SegmentRepository port over a local SQLite file."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def list(
        self, limit: int, offset: int, filters: SegmentFilters
    ) -> SegmentPage:
        return await asyncio.to_thread(self._list_sync, limit, offset, filters)

    async def get_by_id(self, id: int) -> Segment:
        return await asyncio.to_thread(self._get_by_id_sync, id)

    async def facets(self) -> SegmentFacets:
        return await asyncio.to_thread(self._facets_sync)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._db_path, check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con

    def _list_sync(
        self, limit: int, offset: int, filters: SegmentFilters
    ) -> SegmentPage:
        where, params = _where(filters)
        list_sql = f"{_LIST_SELECT} {_FROM} {where} ORDER BY s.id LIMIT ? OFFSET ?"
        count_sql = f"SELECT COUNT(*) {_FROM} {where}"
        con = self._connect()
        try:
            rows = con.execute(list_sql, (*params, limit, offset)).fetchall()
            total = con.execute(count_sql, tuple(params)).fetchone()[0]
        finally:
            con.close()
        items = [
            SegmentSummary(
                id=row["id"],
                segment_id=row["segment_id"],
                sentence=row["sentence"],
                age=row["age"],
                sex=row["sex"],
                speaker_id=row["speaker_id"],
            )
            for row in rows
        ]
        return SegmentPage(items=items, total=total)

    def _facets_sync(self) -> SegmentFacets:
        con = self._connect()
        try:
            values = {
                key: [row[0] for row in con.execute(sql).fetchall()]
                for key, sql in _FACETS_SQL.items()
            }
        finally:
            con.close()
        return SegmentFacets(
            ages=values["ages"],
            sexes=values["sexes"],
            speaker_ids=values["speaker_ids"],
        )

    def _get_by_id_sync(self, id: int) -> Segment:
        con = self._connect()
        try:
            row = con.execute(_DETAIL_SQL, (id,)).fetchone()
        finally:
            con.close()
        if row is None:
            raise SegmentNotFoundError(f"Segment {id} not found.")
        signer = Signer(
            id=row["signer_id"],
            speaker_id=row["speaker_id"],
            sex=row["sex"],
            age=row["age"],
            special_case=row["special_case"],
        )
        video_metadata = VideoMetadata(
            id=row["vm_id"],
            video_id=row["video_id"],
            video_url=row["video_url"],
            subtitles_url=row["subtitles_url"],
            video_type=row["video_type"],
            task_id=row["task_id"],
            speaker_side=row["speaker_side"],
            signer=signer,
        )
        return Segment(
            id=row["segment_pk"],
            segment_id=row["segment_id"],
            sentence=row["sentence"],
            video_metadata=video_metadata,
        )

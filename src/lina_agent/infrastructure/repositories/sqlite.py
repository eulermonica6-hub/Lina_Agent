import asyncio
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from uuid import UUID

from lina_agent.domain.models import CandidateProfile, DomainModel, JobPosting

TableName = Literal["candidate_profiles", "job_postings"]


class _SQLiteJsonStore[ModelT: DomainModel]:
    def __init__(self, database_path: Path, table: TableName, model_type: type[ModelT]) -> None:
        self._database_path = database_path
        self._table = table
        self._model_type = model_type

    async def save(self, entity_id: UUID, entity: ModelT) -> None:
        await asyncio.to_thread(self._save_sync, entity_id, entity.model_dump_json())

    async def get(self, entity_id: UUID) -> ModelT | None:
        payload = await asyncio.to_thread(self._get_sync, entity_id)
        return self._model_type.model_validate_json(payload) if payload is not None else None

    async def list_all(self) -> list[ModelT]:
        payloads = await asyncio.to_thread(self._list_sync)
        return [self._model_type.model_validate_json(payload) for payload in payloads]

    def _save_sync(self, entity_id: UUID, payload: str) -> None:
        with self._connection() as connection:
            connection.execute(
                f"""
                INSERT INTO {self._table} (id, payload)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (str(entity_id), payload),
            )

    def _get_sync(self, entity_id: UUID) -> str | None:
        with self._connection() as connection:
            row = connection.execute(
                f"SELECT payload FROM {self._table} WHERE id = ?",
                (str(entity_id),),
            ).fetchone()
        return str(row[0]) if row is not None else None

    def _list_sync(self) -> list[str]:
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT payload FROM {self._table} ORDER BY rowid"
            ).fetchall()
        return [str(row[0]) for row in rows]

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path, timeout=5)
        try:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table} (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute("PRAGMA user_version = 1")
            yield connection
            connection.commit()
        finally:
            connection.close()


class SQLiteCandidateProfileRepository:
    def __init__(self, database_path: Path) -> None:
        self._store = _SQLiteJsonStore(
            database_path,
            "candidate_profiles",
            CandidateProfile,
        )

    async def save(self, candidate: CandidateProfile) -> None:
        await self._store.save(candidate.id, candidate)

    async def get(self, candidate_id: UUID) -> CandidateProfile | None:
        return await self._store.get(candidate_id)

    async def list_all(self) -> list[CandidateProfile]:
        return await self._store.list_all()


class SQLiteJobPostingRepository:
    def __init__(self, database_path: Path) -> None:
        self._store = _SQLiteJsonStore(
            database_path,
            "job_postings",
            JobPosting,
        )

    async def save(self, job: JobPosting) -> None:
        await self._store.save(job.id, job)

    async def get(self, job_id: UUID) -> JobPosting | None:
        return await self._store.get(job_id)

    async def list_all(self) -> list[JobPosting]:
        return await self._store.list_all()

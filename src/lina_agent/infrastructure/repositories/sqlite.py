import asyncio
import sqlite3
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from uuid import UUID

from lina_agent.application.agent_run_snapshot import AgentRunSnapshot
from lina_agent.application.persistence_models import (
    CandidateConfirmationVersion,
    DocumentReference,
)
from lina_agent.domain.job_applications import JobApplicationRecord
from lina_agent.domain.job_changes import (
    JobCaptureBatch,
    JobChangeEvent,
    JobInboxState,
    JobListingState,
)
from lina_agent.domain.models import CandidateProfile, DomainModel, JobPosting

TableName = Literal[
    "candidate_profiles",
    "job_postings",
    "agent_run_snapshots",
    "document_references",
    "candidate_confirmation_versions",
    "job_capture_batches",
    "job_listing_states",
    "job_change_events",
    "job_inbox_states",
    "job_applications",
]
_SCHEMA_TABLES: tuple[TableName, ...] = (
    "candidate_profiles",
    "job_postings",
    "agent_run_snapshots",
    "document_references",
    "candidate_confirmation_versions",
    "job_capture_batches",
    "job_listing_states",
    "job_change_events",
    "job_inbox_states",
    "job_applications",
)
_SCHEMA_VERSION = 6
_DATABASE_LOCK = threading.RLock()


@contextmanager
def _database_connection(database_path: Path) -> Generator[sqlite3.Connection, None, None]:
    with _DATABASE_LOCK:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path, timeout=5)
        try:
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA journal_mode = WAL")
            for table in _SCHEMA_TABLES:
                connection.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id TEXT PRIMARY KEY,
                        payload TEXT NOT NULL
                    )
                    """
                )
            connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            yield connection
            connection.commit()
        finally:
            connection.close()


class _SQLiteJsonStore[ModelT: DomainModel]:
    def __init__(self, database_path: Path, table: TableName, model_type: type[ModelT]) -> None:
        self._database_path = database_path
        self._table = table
        self._model_type = model_type

    async def save(self, entity_id: UUID | str, entity: ModelT) -> None:
        await asyncio.to_thread(self._save_sync, entity_id, entity.model_dump_json(), True)

    async def save_if_absent(self, entity_id: UUID | str, entity: ModelT) -> None:
        await asyncio.to_thread(self._save_sync, entity_id, entity.model_dump_json(), False)

    async def get(self, entity_id: UUID | str) -> ModelT | None:
        payload = await asyncio.to_thread(self._get_sync, entity_id)
        return self._model_type.model_validate_json(payload) if payload is not None else None

    async def list_all(self) -> list[ModelT]:
        payloads = await asyncio.to_thread(self._list_sync)
        return [self._model_type.model_validate_json(payload) for payload in payloads]

    async def delete(self, entity_id: UUID | str) -> bool:
        return await asyncio.to_thread(self._delete_sync, entity_id)

    def _save_sync(self, entity_id: UUID | str, payload: str, overwrite: bool) -> None:
        conflict_clause = (
            "ON CONFLICT(id) DO UPDATE SET payload = excluded.payload"
            if overwrite
            else "ON CONFLICT(id) DO NOTHING"
        )
        with self._connection() as connection:
            connection.execute(
                f"""
                INSERT INTO {self._table} (id, payload)
                VALUES (?, ?)
                {conflict_clause}
                """,
                (str(entity_id), payload),
            )

    def _get_sync(self, entity_id: UUID | str) -> str | None:
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

    def _delete_sync(self, entity_id: UUID | str) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                f"DELETE FROM {self._table} WHERE id = ?",
                (str(entity_id),),
            )
        return cursor.rowcount > 0

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        with _database_connection(self._database_path) as connection:
            yield connection


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


class SQLiteAgentRunSnapshotRepository:
    def __init__(self, database_path: Path) -> None:
        self._store = _SQLiteJsonStore(
            database_path,
            "agent_run_snapshots",
            AgentRunSnapshot,
        )

    async def save(self, snapshot: AgentRunSnapshot) -> None:
        await self._store.save(snapshot.run_id, snapshot)

    async def get(self, run_id: UUID) -> AgentRunSnapshot | None:
        return await self._store.get(run_id)

    async def list_recent(self, limit: int) -> list[AgentRunSnapshot]:
        snapshots = await self._store.list_all()
        return sorted(snapshots, key=lambda snapshot: snapshot.created_at, reverse=True)[:limit]


class SQLiteDocumentReferenceRepository:
    def __init__(self, database_path: Path) -> None:
        self._store = _SQLiteJsonStore(
            database_path,
            "document_references",
            DocumentReference,
        )

    async def save(self, reference: DocumentReference) -> None:
        await self._store.save_if_absent(reference.reference_id, reference)

    async def get(self, reference_id: UUID) -> DocumentReference | None:
        return await self._store.get(reference_id)


class SQLiteCandidateConfirmationVersionRepository:
    def __init__(self, database_path: Path) -> None:
        self._store = _SQLiteJsonStore(
            database_path,
            "candidate_confirmation_versions",
            CandidateConfirmationVersion,
        )

    async def save(self, version: CandidateConfirmationVersion) -> None:
        await self._store.save(version.version_id, version)

    async def get(self, version_id: UUID) -> CandidateConfirmationVersion | None:
        return await self._store.get(version_id)


class SQLiteJobChangeRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._inbox_store = _SQLiteJsonStore(
            database_path,
            "job_inbox_states",
            JobInboxState,
        )

    async def list_states(self, source_id: str) -> list[JobListingState]:
        payloads = await asyncio.to_thread(
            self._list_payloads_sync,
            "job_listing_states",
            source_id,
        )
        return [JobListingState.model_validate_json(payload) for payload in payloads]

    async def save_capture(
        self,
        batch: JobCaptureBatch,
        states: tuple[JobListingState, ...],
        events: tuple[JobChangeEvent, ...],
    ) -> None:
        await asyncio.to_thread(self._save_capture_sync, batch, states, events)

    async def list_batches(self, source_id: str) -> list[JobCaptureBatch]:
        payloads = await asyncio.to_thread(
            self._list_payloads_sync,
            "job_capture_batches",
            source_id,
        )
        return [JobCaptureBatch.model_validate_json(payload) for payload in payloads]

    async def list_events(self, source_id: str | None = None) -> list[JobChangeEvent]:
        payloads = await asyncio.to_thread(
            self._list_payloads_sync,
            "job_change_events",
            source_id,
        )
        return [JobChangeEvent.model_validate_json(payload) for payload in payloads]

    async def get_inbox_state(self, event_id: UUID) -> JobInboxState | None:
        return await self._inbox_store.get(event_id)

    async def save_inbox_state(self, state: JobInboxState) -> None:
        await self._inbox_store.save(state.event_id, state)

    def _save_capture_sync(
        self,
        batch: JobCaptureBatch,
        states: tuple[JobListingState, ...],
        events: tuple[JobChangeEvent, ...],
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO job_capture_batches (id, payload) VALUES (?, ?)",
                (str(batch.batch_id), batch.model_dump_json()),
            )
            connection.executemany(
                """
                INSERT INTO job_listing_states (id, payload)
                VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                ((state.state_key, state.model_dump_json()) for state in states),
            )
            connection.executemany(
                "INSERT INTO job_change_events (id, payload) VALUES (?, ?)",
                ((str(event.event_id), event.model_dump_json()) for event in events),
            )

    def _list_payloads_sync(
        self,
        table: TableName,
        source_id: str | None,
    ) -> list[str]:
        with self._connection() as connection:
            if source_id is None:
                rows = connection.execute(f"SELECT payload FROM {table} ORDER BY rowid").fetchall()
            else:
                rows = connection.execute(
                    f"""
                    SELECT payload FROM {table}
                    WHERE json_extract(payload, '$.source_id') = ?
                    ORDER BY rowid
                    """,
                    (source_id,),
                ).fetchall()
        return [str(row[0]) for row in rows]

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        with _database_connection(self._database_path) as connection:
            yield connection


class SQLiteJobApplicationRepository:
    def __init__(self, database_path: Path) -> None:
        self._store = _SQLiteJsonStore(
            database_path,
            "job_applications",
            JobApplicationRecord,
        )

    async def save(self, record: JobApplicationRecord) -> None:
        await self._store.save(record.application_key, record)

    async def delete(self, application_key: str) -> bool:
        return await self._store.delete(application_key)

    async def list_all(self) -> list[JobApplicationRecord]:
        return await self._store.list_all()

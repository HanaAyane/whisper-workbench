"""单 sidecar 拥有的 SQLite 任务库，任务快照以事务提交。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.jobs.schemas import JobStatus


class JobStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, timeout=2, check_same_thread=False)
        try:
            # 独占连接同时防止第二个 sidecar 把仍在运行的任务恢复为已中断。
            self._db.execute("PRAGMA locking_mode=EXCLUSIVE")
            with self._db:
                self._db.execute("BEGIN EXCLUSIVE")
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS jobs ("
                    "id TEXT PRIMARY KEY, state TEXT NOT NULL, snapshot TEXT NOT NULL)"
                )
        except sqlite3.Error:
            self._db.close()
            raise

    def get(self, job_id: str) -> JobStatus:
        row = self._db.execute("SELECT snapshot FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return JobStatus.model_validate_json(row[0])

    def list(self, *, active_only: bool = False) -> list[JobStatus]:
        query = "SELECT snapshot FROM jobs"
        if active_only:
            query += " WHERE state IN ('queued', 'running')"
        rows = self._db.execute(query + " ORDER BY rowid DESC")
        return [JobStatus.model_validate_json(row[0]) for row in rows]

    def save(self, *jobs: JobStatus) -> None:
        with self._db:
            self._db.executemany(
                "INSERT INTO jobs(id, state, snapshot) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET state=excluded.state, snapshot=excluded.snapshot",
                ((job.id, job.state, job.model_dump_json()) for job in jobs),
            )

    def close(self) -> None:
        self._db.close()

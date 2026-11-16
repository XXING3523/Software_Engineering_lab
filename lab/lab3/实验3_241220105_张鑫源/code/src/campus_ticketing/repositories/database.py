"""SQLite 连接、事务和数据库初始化。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    roles TEXT NOT NULL,
    password_hash TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1))
);

CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    organizer_id INTEGER NOT NULL REFERENCES users(id),
    description TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    report_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    remaining_capacity INTEGER NOT NULL CHECK (remaining_capacity BETWEEN 0 AND capacity),
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ticket_types (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    price TEXT NOT NULL,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    remaining_capacity INTEGER NOT NULL CHECK (remaining_capacity BETWEEN 0 AND capacity),
    status TEXT NOT NULL,
    UNIQUE(session_id, name)
);

CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    activity_id INTEGER NOT NULL REFERENCES activities(id),
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    ticket_type_id INTEGER NOT NULL REFERENCES ticket_types(id),
    status TEXT NOT NULL,
    request_id TEXT NOT NULL UNIQUE,
    ticket_code TEXT UNIQUE,
    activity_snapshot TEXT NOT NULL,
    session_snapshot TEXT NOT NULL,
    ticket_snapshot TEXT NOT NULL,
    created_at TEXT NOT NULL,
    cancelled_at TEXT
);

CREATE TABLE IF NOT EXISTS waitlist_entries (
    id INTEGER PRIMARY KEY,
    registration_id INTEGER NOT NULL UNIQUE REFERENCES registrations(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER PRIMARY KEY,
    registration_id INTEGER NOT NULL UNIQUE REFERENCES registrations(id),
    checker_id INTEGER NOT NULL REFERENCES users(id),
    checked_at TEXT NOT NULL,
    method TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    activity_id INTEGER REFERENCES activities(id),
    registration_id INTEGER REFERENCES registrations(id),
    sent_at TEXT,
    read_at TEXT,
    status TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY,
    operator_id INTEGER NOT NULL REFERENCES users(id),
    action TEXT NOT NULL,
    before_state TEXT NOT NULL,
    after_state TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activity_status ON activities(status);
CREATE INDEX IF NOT EXISTS idx_session_activity ON sessions(activity_id);
CREATE INDEX IF NOT EXISTS idx_ticket_session ON ticket_types(session_id);
CREATE INDEX IF NOT EXISTS idx_registration_user ON registrations(user_id);
CREATE INDEX IF NOT EXISTS idx_registration_session_status
    ON registrations(session_id, status);
CREATE INDEX IF NOT EXISTS idx_waitlist_position
    ON waitlist_entries(registration_id, position);
CREATE INDEX IF NOT EXISTS idx_notification_user_status
    ON notifications(user_id, status);
CREATE INDEX IF NOT EXISTS idx_audit_operator ON audit_logs(operator_id);
"""


class Database:
    """对 SQLite 数据库提供连接和事务管理。"""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._connection: sqlite3.Connection | None = None
        self._transaction_depth = 0

    def connect(self) -> sqlite3.Connection:
        """建立连接，并开启外键约束。"""

        if self._connection is None:
            self._connection = sqlite3.connect(self.path)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA busy_timeout = 5000")
        return self._connection

    def initialize(self) -> None:
        """创建全部表和索引。"""

        connection = self.connect()
        connection.executescript(SCHEMA)
        connection.commit()

    @contextmanager
    def transaction(self, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        """以事务方式执行一组操作。"""

        connection = self.connect()
        outermost = self._transaction_depth == 0
        if outermost:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        self._transaction_depth += 1
        try:
            yield connection
        except Exception:
            if outermost:
                connection.rollback()
            raise
        else:
            if outermost:
                connection.commit()
        finally:
            self._transaction_depth -= 1

    def commit_if_needed(self) -> None:
        """在不受外层事务控制时提交一次写操作。"""

        if self._transaction_depth == 0:
            self.connect().commit()

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
        """执行一条写入或查询语句。"""

        return self.connect().execute(sql, parameters)

    def query_all(
        self, sql: str, parameters: tuple[object, ...] = ()
    ) -> list[sqlite3.Row]:
        """查询多行记录。"""

        return list(self.connect().execute(sql, parameters).fetchall())

    def query_one(
        self, sql: str, parameters: tuple[object, ...] = ()
    ) -> sqlite3.Row | None:
        """查询单行记录。"""

        return self.connect().execute(sql, parameters).fetchone()

    def close(self) -> None:
        """关闭连接。"""

        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> "Database":
        self.initialize()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

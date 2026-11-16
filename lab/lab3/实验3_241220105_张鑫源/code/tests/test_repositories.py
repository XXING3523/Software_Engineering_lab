"""SQLite 数据层测试。"""

import sqlite3
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from campus_ticketing.domain import (
    Activity,
    Registration,
    Role,
    Session,
    Snapshot,
    TicketType,
    User,
    WaitlistEntry,
)
from campus_ticketing.domain.enums import RegistrationStatus
from campus_ticketing.repositories import Database, RepositoryBundle


class RepositoryTests(unittest.TestCase):
    """验证对象持久化、约束和事务行为。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.sqlite3")
        self.repositories = RepositoryBundle(self.database)
        self.user = User(1, "组织者", {Role.ORGANIZER}, username="organizer")
        self.participant = User(2, "参与者", {Role.PARTICIPANT}, username="participant")
        self.repositories.users.add(self.user)
        self.repositories.users.add(self.participant)

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def _create_ticket_context(self) -> tuple[Activity, Session, TicketType]:
        activity = Activity(10, "校园讲座", 1, location="教学楼")
        session = Session(
            11,
            activity.id,
            datetime(2026, 11, 20, 9, 0),
            datetime(2026, 11, 20, 11, 0),
            2,
        )
        ticket = TicketType(12, session.id, "普通票", Decimal("0"), 2)
        self.repositories.activities.add(activity)
        self.repositories.sessions.add(session)
        self.repositories.tickets.add(ticket)
        return activity, session, ticket

    def test_schema_contains_all_uml_persistence_tables(self) -> None:
        rows = self.database.query_all(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
        names = {row["name"] for row in rows}
        self.assertTrue(
            {
                "users",
                "activities",
                "sessions",
                "ticket_types",
                "registrations",
                "waitlist_entries",
                "checkins",
                "notifications",
                "audit_logs",
            }.issubset(names)
        )

    def test_activity_graph_round_trip(self) -> None:
        activity, session, ticket = self._create_ticket_context()
        loaded_activity = self.repositories.activities.get(activity.id)
        loaded_session = self.repositories.sessions.get(session.id)
        loaded_ticket = self.repositories.tickets.get(ticket.id)
        self.assertEqual(loaded_activity.title, activity.title)
        self.assertEqual(loaded_session.activity_id, activity.id)
        self.assertEqual(loaded_ticket.price, Decimal("0"))

    def test_registration_snapshot_and_waitlist_round_trip(self) -> None:
        activity, session, ticket = self._create_ticket_context()
        snapshot = Snapshot(activity.title, ticket.name, ticket.price)
        registration = Registration.create_waitlist(
            self.participant.id,
            activity.id,
            session.id,
            ticket.id,
            "request-repository-1",
            snapshot,
            snapshot,
            snapshot,
        )
        self.repositories.registrations.add(registration)
        entry = WaitlistEntry(20, registration.id, 1)
        self.repositories.registrations.add_waitlist_entry(entry)
        loaded = self.repositories.registrations.by_request_id("request-repository-1")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.status, RegistrationStatus.WAITLISTED)
        self.assertEqual(loaded.ticket_snapshot.price, Decimal("0"))
        self.assertEqual(
            self.repositories.registrations.next_waitlist(session.id).id,
            registration.id,
        )

    def test_request_id_is_unique(self) -> None:
        activity, session, ticket = self._create_ticket_context()
        snapshot = Snapshot(activity.title, ticket.name, ticket.price)
        first = Registration.create(
            self.participant.id,
            activity.id,
            session.id,
            ticket.id,
            "same-request",
            snapshot,
            snapshot,
            snapshot,
        )
        self.repositories.registrations.add(first)
        second = Registration.create(
            self.participant.id,
            activity.id,
            session.id,
            ticket.id,
            "same-request",
            snapshot,
            snapshot,
            snapshot,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.repositories.registrations.add(second)

    def test_transaction_rolls_back_all_writes(self) -> None:
        activity = Activity(30, "事务测试活动", 1)
        with self.assertRaises(RuntimeError):
            with self.database.transaction(immediate=True):
                self.repositories.activities.add(activity)
                raise RuntimeError("force rollback")
        with self.assertRaises(Exception):
            self.repositories.activities.get(activity.id)


if __name__ == "__main__":
    unittest.main()

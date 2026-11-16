"""领域对象和状态机测试。"""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from campus_ticketing.domain import (
    Activity,
    ActivityStatus,
    Registration,
    RegistrationStatus,
    Role,
    Session,
    Snapshot,
    TicketType,
    User,
)
from campus_ticketing.domain.exceptions import (
    CapacityError,
    InvalidTransitionError,
    ValidationError,
)
from campus_ticketing.domain.state_machine import transition


class DomainEntityTests(unittest.TestCase):
    """验证领域对象的基本不变量。"""

    def setUp(self) -> None:
        self.start = datetime(2026, 11, 20, 10, 0)
        self.end = self.start + timedelta(hours=2)
        self.activity = Activity(1, "校园羽毛球赛", 2)
        self.session = Session(3, 1, self.start, self.end, 2)
        self.ticket = TicketType(4, 3, "普通票", Decimal("0"), 2)

    def test_user_role_and_admin_privilege(self) -> None:
        user = User(1, "小明", {Role.PARTICIPANT})
        self.assertTrue(user.has_role(Role.PARTICIPANT))
        self.assertFalse(user.has_role(Role.ORGANIZER))
        user.add_role(Role.ADMIN)
        self.assertTrue(user.has_role(Role.ORGANIZER))

    def test_activity_requires_session_before_publish(self) -> None:
        self.activity.submit_review()
        with self.assertRaises(ValidationError):
            self.activity.publish()
        self.activity.sessions.append(self.session)
        self.activity.publish()
        self.assertEqual(self.activity.status, ActivityStatus.PUBLISHED)

    def test_session_and_ticket_capacity_cannot_be_overdrawn(self) -> None:
        self.session.open()
        self.session.reserve()
        self.session.reserve()
        self.assertEqual(self.session.remaining_capacity, 0)
        with self.assertRaises(CapacityError):
            self.session.reserve()
        self.ticket.reserve()
        self.ticket.reserve()
        with self.assertRaises(CapacityError):
            self.ticket.reserve()

    def test_registration_lifecycle(self) -> None:
        snap = Snapshot("校园羽毛球赛", "普通票", Decimal("0"))
        registration = Registration.create(
            1,
            1,
            3,
            4,
            "request-1",
            snap,
            snap,
            snap,
        )
        self.assertEqual(registration.status, RegistrationStatus.REGISTERED)
        self.assertTrue(registration.ticket_code.startswith("T-"))
        registration.cancel()
        self.assertEqual(registration.status, RegistrationStatus.CANCELLED)
        with self.assertRaises(ValidationError):
            registration.cancel()

    def test_waitlist_can_promote_once(self) -> None:
        snap = Snapshot("校园羽毛球赛", "普通票")
        registration = Registration.create_waitlist(
            1,
            1,
            3,
            4,
            "request-2",
            snap,
            snap,
            snap,
        )
        registration.promote()
        self.assertEqual(registration.status, RegistrationStatus.REGISTERED)
        self.assertTrue(registration.ticket_code)
        with self.assertRaises(ValidationError):
            registration.promote()

    def test_state_machine_rejects_invalid_transition(self) -> None:
        self.assertEqual(
            transition(RegistrationStatus.WAITLISTED, RegistrationStatus.REGISTERED),
            RegistrationStatus.REGISTERED,
        )
        with self.assertRaises(InvalidTransitionError):
            transition(RegistrationStatus.CANCELLED, RegistrationStatus.REGISTERED)


if __name__ == "__main__":
    unittest.main()

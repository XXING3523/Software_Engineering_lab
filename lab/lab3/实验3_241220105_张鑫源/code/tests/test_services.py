"""业务服务集成测试。"""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from campus_ticketing.domain.enums import RegistrationStatus, Role
from campus_ticketing.domain.exceptions import PermissionDeniedError
from campus_ticketing.repositories import Database, RepositoryBundle
from campus_ticketing.scheduler import SchedulerService
from campus_ticketing.services import (
    ActivityService,
    AuditService,
    AuthService,
    CheckInService,
    NotificationService,
    RegistrationService,
    ReportingService,
)


class ServiceIntegrationTests(unittest.TestCase):
    """验证从活动发布到报名签到的完整业务链路。"""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database = Database(Path(self.temp_dir.name) / "services.sqlite3")
        self.repositories = RepositoryBundle(database)
        self.auth = AuthService(self.repositories)
        self.audit = AuditService(self.repositories)
        self.notifications = NotificationService(self.repositories)
        self.activities = ActivityService(self.repositories, self.audit)
        self.registrations = RegistrationService(
            self.repositories, self.notifications, self.audit
        )
        self.checkins = CheckInService(
            self.repositories, self.notifications, self.audit
        )
        self.reporting = ReportingService(self.repositories)
        self.scheduler = SchedulerService(
            self.repositories, self.notifications, self.audit
        )
        self.users = self.auth.ensure_demo_users()
        self.participant = self.users[0]
        self.organizer = self.users[1]
        self.checker = self.users[2]
        self.admin = self.users[3]
        self.activity, self.session, self.ticket = self._publish_activity(1)

    def tearDown(self) -> None:
        self.repositories.database.close()
        self.temp_dir.cleanup()

    def _publish_activity(self, capacity: int):
        activity = self.activities.create_activity(
            self.organizer, "软件工程分享会", "介绍项目实现过程", "教学楼 A101"
        )
        start = datetime(2026, 11, 20, 9, 0)
        session = self.activities.add_session(
            self.organizer, activity.id, start, start + timedelta(hours=2), capacity
        )
        ticket = self.activities.add_ticket_type(
            self.organizer, session.id, "普通票", "0", capacity
        )
        self.activities.submit_review(self.organizer, activity.id)
        self.activities.review_activity(self.admin, activity.id, True)
        return activity, session, ticket

    def test_complete_registration_and_idempotency(self) -> None:
        first = self.registrations.register(
            self.participant,
            self.activity.id,
            self.session.id,
            self.ticket.id,
            "service-request-1",
        )
        second = self.registrations.register(
            self.participant,
            self.activity.id,
            self.session.id,
            self.ticket.id,
            "service-request-1",
        )
        self.assertEqual(first.status, "registered")
        self.assertEqual(first.registration.id, second.registration.id)
        self.assertTrue(second.idempotent)
        self.assertEqual(len(self.registrations.list_for_user(self.participant)), 1)

    def test_full_capacity_waitlist_and_promotion(self) -> None:
        first = self.registrations.register(
            self.participant,
            self.activity.id,
            self.session.id,
            self.ticket.id,
            "service-request-2",
        )
        second_user = self.auth.register(
            "participant2", "第二参与者", "1234", {Role.PARTICIPANT}
        )
        second = self.registrations.register(
            second_user,
            self.activity.id,
            self.session.id,
            self.ticket.id,
            "service-request-3",
        )
        self.assertEqual(first.status, "registered")
        self.assertEqual(second.status, "waitlisted")
        cancelled = self.registrations.cancel(self.participant, first.registration.id)
        self.assertEqual(cancelled.status, "cancelled_and_promoted")
        promoted = self.repositories.registrations.get(second.registration.id)
        self.assertEqual(promoted.status, RegistrationStatus.REGISTERED)
        self.assertTrue(promoted.ticket_code)

    def test_only_checker_or_admin_can_check_in(self) -> None:
        result = self.registrations.register(
            self.participant,
            self.activity.id,
            self.session.id,
            self.ticket.id,
            "service-request-4",
        )
        with self.assertRaises(PermissionDeniedError):
            self.checkins.check_in(self.participant, result.registration.ticket_code)
        check_in = self.checkins.check_in(
            self.checker, result.registration.ticket_code
        )
        self.assertEqual(check_in.registration_id, result.registration.id)
        self.assertEqual(
            self.repositories.registrations.get(result.registration.id).status,
            RegistrationStatus.CHECKED_IN,
        )

    def test_admin_statistics_and_export(self) -> None:
        self.registrations.register(
            self.participant,
            self.activity.id,
            self.session.id,
            self.ticket.id,
            "service-request-5",
        )
        statistics = self.reporting.statistics(self.admin)
        self.assertEqual(statistics[RegistrationStatus.REGISTERED.value], 1)
        target = Path(self.temp_dir.name) / "registrations.csv"
        output = self.reporting.export_registrations(self.organizer, self.activity.id, target)
        self.assertEqual(output, target)
        self.assertIn("ticket_code", target.read_text(encoding="utf-8-sig"))

    def test_scheduler_marks_old_registration_absent(self) -> None:
        result = self.registrations.register(
            self.participant,
            self.activity.id,
            self.session.id,
            self.ticket.id,
            "service-request-6",
        )
        old_end = datetime(2026, 11, 1, 10, 0)
        session = self.repositories.sessions.get(self.session.id)
        session.start_at = old_end - timedelta(hours=2)
        session.end_at = old_end
        self.repositories.sessions.update(session)
        changed = self.scheduler.mark_absent(
            self.admin, datetime(2026, 11, 2, 13, 0)
        )
        self.assertEqual(changed, 1)
        self.assertEqual(
            self.repositories.registrations.get(result.registration.id).status,
            RegistrationStatus.ABSENT,
        )


if __name__ == "__main__":
    unittest.main()

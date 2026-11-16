"""候补与缺席的定时处理。"""

from __future__ import annotations

from datetime import datetime, timedelta

from campus_ticketing.domain.entities import User
from campus_ticketing.domain.enums import RegistrationStatus, Role, SessionStatus
from campus_ticketing.repositories import RepositoryBundle

from campus_ticketing.services.audit_service import AuditService
from campus_ticketing.services.authorization import require_role
from campus_ticketing.services.notification_service import NotificationService


class SchedulerService:
    """模拟组件图中的 Scheduler。"""

    def __init__(
        self,
        repositories: RepositoryBundle,
        notifications: NotificationService,
        audit: AuditService,
    ) -> None:
        self.repositories = repositories
        self.notifications = notifications
        self.audit = audit

    def mark_absent(self, actor: User, now: datetime | None = None) -> int:
        """将结束两小时后仍未签到的报名标记为缺席。"""

        require_role(actor, Role.ADMIN)
        current = now or datetime.now().replace(microsecond=0)
        changed = 0
        for session in self._all_sessions():
            if session.status == SessionStatus.FINISHED:
                cutoff = session.end_at + timedelta(hours=2)
                if current < cutoff:
                    continue
            elif current < session.end_at + timedelta(hours=2):
                continue
            for registration in self.repositories.registrations.list_by_session(
                session.id, RegistrationStatus.REGISTERED
            ):
                registration.mark_absent()
                self.repositories.registrations.update(registration)
                self.notifications.send(
                    registration.user_id,
                    "报名记录已标记缺席",
                    "场次结束后仍未签到，系统已将本次报名标记为缺席。",
                    registration.activity_id,
                    registration.id,
                )
                self.audit.record(actor, "mark_absent", "registered", "absent")
                changed += 1
            session.status = SessionStatus.FINISHED
            self.repositories.sessions.update(session)
        return changed

    def _all_sessions(self):
        rows = self.repositories.database.query_all("SELECT * FROM sessions ORDER BY start_at")
        return [self.repositories.sessions.get(row["id"]) for row in rows]

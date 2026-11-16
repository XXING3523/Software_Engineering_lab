"""票码签到服务。"""

from __future__ import annotations

from campus_ticketing.domain.entities import CheckIn, User, new_id
from campus_ticketing.domain.enums import CheckInMethod, RegistrationStatus, Role
from campus_ticketing.domain.exceptions import ValidationError
from campus_ticketing.repositories import RepositoryBundle

from .audit_service import AuditService
from .authorization import require_any_role
from .notification_service import NotificationService


class CheckInService:
    """验证票码并完成签到。"""

    def __init__(
        self,
        repositories: RepositoryBundle,
        notifications: NotificationService,
        audit: AuditService,
    ) -> None:
        self.repositories = repositories
        self.notifications = notifications
        self.audit = audit

    def check_in(
        self,
        actor: User,
        ticket_code: str,
        method: CheckInMethod = CheckInMethod.MANUAL,
    ) -> CheckIn:
        """检查票码并写入签到记录。"""

        require_any_role(actor, Role.CHECKER, Role.ADMIN)
        with self.repositories.database.transaction(immediate=True):
            registration = self.repositories.registrations.by_ticket_code(ticket_code.strip())
            if registration is None:
                raise ValidationError("票码不存在")
            if registration.status != RegistrationStatus.REGISTERED:
                raise ValidationError("当前报名状态不能签到")
            if self.repositories.checkins.by_registration(registration.id) is not None:
                raise ValidationError("该报名已经签到")
            before = registration.status.value
            registration.mark_checked_in()
            self.repositories.registrations.update(registration)
            check_in = CheckIn(new_id(), registration.id, actor.id, method=method)
            if not check_in.verify():
                raise ValidationError("签到记录无效")
            self.repositories.checkins.add(check_in)
            self.notifications.send(
                registration.user_id,
                "签到成功",
                "你的活动签到已完成。",
                registration.activity_id,
                registration.id,
            )
            self.audit.record(actor, "check_in", before, registration.status.value)
            return check_in

"""报名、取消、候补和自动递补服务。"""

from __future__ import annotations

from dataclasses import dataclass

from campus_ticketing.domain.entities import (
    Activity,
    Registration,
    Session,
    Snapshot,
    TicketType,
    User,
    WaitlistEntry,
    new_id,
)
from campus_ticketing.domain.enums import (
    ActivityStatus,
    RegistrationStatus,
    Role,
    SessionStatus,
    TicketStatus,
)
from campus_ticketing.domain.exceptions import (
    ConflictError,
    PermissionDeniedError,
    ValidationError,
)
from campus_ticketing.repositories import RepositoryBundle

from .audit_service import AuditService
from .authorization import require_any_role
from .notification_service import NotificationService


@dataclass(slots=True)
class RegistrationResult:
    """报名操作返回值。"""

    status: str
    message: str
    registration: Registration | None = None
    waitlist_position: int | None = None
    idempotent: bool = False


class RegistrationService:
    """实现报名时序图中的事务和幂等逻辑。"""

    def __init__(
        self,
        repositories: RepositoryBundle,
        notifications: NotificationService,
        audit: AuditService,
    ) -> None:
        self.repositories = repositories
        self.notifications = notifications
        self.audit = audit

    def register(
        self,
        actor: User,
        activity_id: int,
        session_id: int,
        ticket_type_id: int,
        request_id: str,
        waitlist_enabled: bool = True,
    ) -> RegistrationResult:
        """提交报名，名额不足时进入候补。"""

        require_any_role(actor, Role.PARTICIPANT, Role.ADMIN)
        if not request_id.strip():
            raise ValidationError("requestId 不能为空")
        with self.repositories.database.transaction(immediate=True):
            existing = self.repositories.registrations.by_request_id(request_id)
            if existing is not None:
                return RegistrationResult(
                    status=existing.status.value,
                    message="重复请求，返回第一次报名结果",
                    registration=existing,
                    idempotent=True,
                )
            activity = self.repositories.activities.get(activity_id)
            session = self.repositories.sessions.get(session_id)
            ticket = self.repositories.tickets.get(ticket_type_id)
            self._validate_target(activity, session, ticket)
            snapshots = self._snapshots(activity, session, ticket)
            if self._has_capacity(session, ticket):
                session.reserve()
                ticket.reserve()
                registration = Registration.create(
                    actor.id,
                    activity.id,
                    session.id,
                    ticket.id,
                    request_id,
                    *snapshots,
                )
                self.repositories.sessions.update(session)
                self.repositories.tickets.update(ticket)
                self.repositories.registrations.add(registration)
                self.notifications.send(
                    actor.id,
                    "报名成功",
                    f"你已成功报名活动“{activity.title}”，票码为 {registration.ticket_code}",
                    activity.id,
                    registration.id,
                )
                self.audit.record(actor, "create_registration", None, registration)
                return RegistrationResult("registered", "报名成功", registration)
            if not waitlist_enabled:
                return RegistrationResult("failed", "名额已满且未开放候补")
            registration = Registration.create_waitlist(
                actor.id,
                activity.id,
                session.id,
                ticket.id,
                request_id,
                *snapshots,
            )
            position = self.repositories.registrations.waitlist_position(session.id)
            self.repositories.registrations.add(registration)
            self.repositories.registrations.add_waitlist_entry(
                WaitlistEntry(new_id(), registration.id, position)
            )
            self.notifications.send(
                actor.id,
                "已加入候补",
                f"活动“{activity.title}”当前已满，你的候补序号为 {position}",
                activity.id,
                registration.id,
            )
            self.audit.record(actor, "create_waitlist_registration", None, registration)
            return RegistrationResult(
                "waitlisted",
                f"名额已满，已进入候补，当前序号为 {position}",
                registration,
                position,
            )

    def cancel(self, actor: User, registration_id: int) -> RegistrationResult:
        """取消报名，并在需要时递补候补用户。"""

        require_any_role(actor, Role.PARTICIPANT, Role.ADMIN)
        with self.repositories.database.transaction(immediate=True):
            registration = self.repositories.registrations.get(registration_id)
            self._check_owner(actor, registration.user_id)
            before = registration.status.value
            session = self.repositories.sessions.get(registration.session_id)
            ticket = self.repositories.tickets.get(registration.ticket_type_id)
            registration.cancel()
            self.repositories.registrations.update(registration)
            if before == RegistrationStatus.REGISTERED.value:
                session.release()
                ticket.release()
                self.repositories.sessions.update(session)
                self.repositories.tickets.update(ticket)
                self.notifications.send(
                    registration.user_id,
                    "报名已取消",
                    "你的报名已取消，名额将按候补顺序释放。",
                    registration.activity_id,
                    registration.id,
                )
                promoted = self._promote_next(session, ticket)
                self.audit.record(actor, "cancel_registration", before, registration.status.value)
                if promoted is not None:
                    return RegistrationResult(
                        "cancelled_and_promoted",
                        "报名已取消，候补用户已自动递补",
                        registration,
                    )
            else:
                self.repositories.registrations.remove_waitlist_entry(registration.id)
                self.notifications.send(
                    registration.user_id,
                    "候补已取消",
                    "你的候补报名已取消。",
                    registration.activity_id,
                    registration.id,
                )
                self.audit.record(actor, "cancel_waitlist", before, registration.status.value)
            return RegistrationResult("cancelled", "报名已取消", registration)

    def list_for_user(self, actor: User) -> list[Registration]:
        """查询当前用户的报名。"""

        require_any_role(actor, Role.PARTICIPANT, Role.ADMIN)
        return self.repositories.registrations.list_by_user(actor.id)

    def find_by_ticket_code(self, ticket_code: str) -> Registration | None:
        """根据票码查询报名。"""

        return self.repositories.registrations.by_ticket_code(ticket_code.strip())

    def _promote_next(self, session: Session, ticket: TicketType) -> Registration | None:
        candidate = self.repositories.registrations.next_waitlist(session.id)
        if candidate is None:
            return None
        if not self._has_capacity(session, ticket):
            return None
        session.reserve()
        ticket.reserve()
        candidate.promote()
        self.repositories.sessions.update(session)
        self.repositories.tickets.update(ticket)
        self.repositories.registrations.update(candidate)
        self.repositories.registrations.remove_waitlist_entry(candidate.id)
        self.notifications.send(
            candidate.user_id,
            "候补递补成功",
            f"你已递补成功，票码为 {candidate.ticket_code}",
            candidate.activity_id,
            candidate.id,
        )
        return candidate

    @staticmethod
    def _has_capacity(session: Session, ticket: TicketType) -> bool:
        return bool(
            session.status == SessionStatus.OPEN
            and ticket.status == TicketStatus.ACTIVE
            and session.remaining_capacity
            and ticket.remaining_capacity
        )

    @staticmethod
    def _snapshots(
        activity: Activity, session: Session, ticket: TicketType
    ) -> tuple[Snapshot, Snapshot, Snapshot]:
        return (
            Snapshot(
                activity.title,
                activity.title,
                metadata={"location": activity.location},
            ),
            Snapshot(
                activity.title,
                f"场次 {session.id}",
                metadata={
                    "start_at": session.start_at.isoformat(sep=" "),
                    "end_at": session.end_at.isoformat(sep=" "),
                },
            ),
            Snapshot(activity.title, ticket.name, ticket.price),
        )

    @staticmethod
    def _validate_target(activity: Activity, session: Session, ticket: TicketType) -> None:
        if activity.status != ActivityStatus.PUBLISHED:
            raise ConflictError("活动尚未发布或已经关闭")
        if session.activity_id != activity.id:
            raise ValidationError("场次不属于该活动")
        if ticket.session_id != session.id:
            raise ValidationError("票种不属于该场次")
        if session.status not in {SessionStatus.OPEN, SessionStatus.FULL}:
            raise ConflictError("场次当前未开放报名")
        if ticket.status not in {TicketStatus.ACTIVE, TicketStatus.SOLD_OUT}:
            raise ConflictError("票种当前不可报名或候补")

    @staticmethod
    def _check_owner(actor: User, owner_id: int) -> None:
        if actor.id != owner_id and not actor.has_role(Role.ADMIN):
            raise PermissionDeniedError("不能操作其他用户的报名")

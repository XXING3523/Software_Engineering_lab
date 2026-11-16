"""各领域对象的 SQLite 仓储。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from decimal import Decimal

from campus_ticketing.domain.entities import (
    Activity,
    AuditLog,
    CheckIn,
    Notification,
    Registration,
    Session,
    TicketType,
    User,
    WaitlistEntry,
)
from campus_ticketing.domain.enums import (
    ActivityStatus,
    CheckInMethod,
    NotificationStatus,
    RegistrationStatus,
    Role,
    SessionStatus,
    TicketStatus,
)
from campus_ticketing.domain.exceptions import NotFoundError
from campus_ticketing.repositories.database import Database
from campus_ticketing.repositories.serializers import (
    dt_to_text,
    roles_from_text,
    roles_to_text,
    snapshot_from_text,
    snapshot_to_text,
    text_to_dt,
)


def require_row(row: sqlite3.Row | None, label: str) -> sqlite3.Row:
    """在查询不到对象时抛出统一异常。"""

    if row is None:
        raise NotFoundError(f"找不到{label}")
    return row


class UserRepository:
    """用户仓储。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, user: User) -> User:
        self.database.execute(
            "INSERT INTO users(id, username, name, roles, password_hash, enabled) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                user.id,
                user.username,
                user.name,
                roles_to_text({role.value for role in user.roles}),
                user.password_hash,
                int(user.enabled),
            ),
        )
        self.database.commit_if_needed()
        return user

    def get(self, user_id: int) -> User:
        return self._from_row(require_row(
            self.database.query_one("SELECT * FROM users WHERE id = ?", (user_id,)),
            "用户",
        ))

    def by_username(self, username: str) -> User | None:
        row = self.database.query_one(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        return self._from_row(row) if row else None

    def list_all(self) -> list[User]:
        return [self._from_row(row) for row in self.database.query_all(
            "SELECT * FROM users ORDER BY id"
        )]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> User:
        return User(
            id=row["id"],
            username=row["username"],
            name=row["name"],
            roles={Role(value) for value in roles_from_text(row["roles"])},
            password_hash=row["password_hash"],
            enabled=bool(row["enabled"]),
        )


class ActivityRepository:
    """活动仓储。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, activity: Activity) -> Activity:
        self.database.execute(
            "INSERT INTO activities(id, title, organizer_id, description, location, "
            "status, report_reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                activity.id,
                activity.title,
                activity.organizer_id,
                activity.description,
                activity.location,
                activity.status.value,
                activity.report_reason,
                dt_to_text(activity.created_at),
            ),
        )
        self.database.commit_if_needed()
        return activity

    def get(self, activity_id: int) -> Activity:
        return self._from_row(require_row(
            self.database.query_one("SELECT * FROM activities WHERE id = ?", (activity_id,)),
            "活动",
        ))

    def update(self, activity: Activity) -> Activity:
        self.database.execute(
            "UPDATE activities SET title = ?, description = ?, location = ?, "
            "status = ?, report_reason = ? WHERE id = ?",
            (
                activity.title,
                activity.description,
                activity.location,
                activity.status.value,
                activity.report_reason,
                activity.id,
            ),
        )
        self.database.commit_if_needed()
        return activity

    def list_by_status(self, status: ActivityStatus | None = None) -> list[Activity]:
        if status is None:
            rows = self.database.query_all("SELECT * FROM activities ORDER BY id")
        else:
            rows = self.database.query_all(
                "SELECT * FROM activities WHERE status = ? ORDER BY id", (status.value,)
            )
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Activity:
        return Activity(
            id=row["id"],
            title=row["title"],
            organizer_id=row["organizer_id"],
            description=row["description"],
            location=row["location"],
            status=ActivityStatus(row["status"]),
            report_reason=row["report_reason"],
            created_at=text_to_dt(row["created_at"]),
        )


class SessionRepository:
    """场次仓储。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, session: Session) -> Session:
        self.database.execute(
            "INSERT INTO sessions(id, activity_id, start_at, end_at, capacity, "
            "remaining_capacity, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session.id,
                session.activity_id,
                dt_to_text(session.start_at),
                dt_to_text(session.end_at),
                session.capacity,
                session.remaining_capacity,
                session.status.value,
            ),
        )
        self.database.commit_if_needed()
        return session

    def get(self, session_id: int) -> Session:
        return self._from_row(require_row(
            self.database.query_one("SELECT * FROM sessions WHERE id = ?", (session_id,)),
            "场次",
        ))

    def update(self, session: Session) -> Session:
        self.database.execute(
            "UPDATE sessions SET start_at = ?, end_at = ?, capacity = ?, "
            "remaining_capacity = ?, status = ? WHERE id = ?",
            (
                dt_to_text(session.start_at),
                dt_to_text(session.end_at),
                session.capacity,
                session.remaining_capacity,
                session.status.value,
                session.id,
            ),
        )
        self.database.commit_if_needed()
        return session

    def list_by_activity(self, activity_id: int) -> list[Session]:
        rows = self.database.query_all(
            "SELECT * FROM sessions WHERE activity_id = ? ORDER BY start_at",
            (activity_id,),
        )
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            activity_id=row["activity_id"],
            start_at=text_to_dt(row["start_at"]),
            end_at=text_to_dt(row["end_at"]),
            capacity=row["capacity"],
            remaining_capacity=row["remaining_capacity"],
            status=SessionStatus(row["status"]),
        )


class TicketTypeRepository:
    """票种仓储。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, ticket: TicketType) -> TicketType:
        self.database.execute(
            "INSERT INTO ticket_types(id, session_id, name, price, capacity, "
            "remaining_capacity, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                ticket.id,
                ticket.session_id,
                ticket.name,
                str(ticket.price),
                ticket.capacity,
                ticket.remaining_capacity,
                ticket.status.value,
            ),
        )
        self.database.commit_if_needed()
        return ticket

    def get(self, ticket_id: int) -> TicketType:
        return self._from_row(require_row(
            self.database.query_one("SELECT * FROM ticket_types WHERE id = ?", (ticket_id,)),
            "票种",
        ))

    def update(self, ticket: TicketType) -> TicketType:
        self.database.execute(
            "UPDATE ticket_types SET name = ?, price = ?, capacity = ?, "
            "remaining_capacity = ?, status = ? WHERE id = ?",
            (
                ticket.name,
                str(ticket.price),
                ticket.capacity,
                ticket.remaining_capacity,
                ticket.status.value,
                ticket.id,
            ),
        )
        self.database.commit_if_needed()
        return ticket

    def list_by_session(self, session_id: int) -> list[TicketType]:
        rows = self.database.query_all(
            "SELECT * FROM ticket_types WHERE session_id = ? ORDER BY id", (session_id,)
        )
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> TicketType:
        return TicketType(
            id=row["id"],
            session_id=row["session_id"],
            name=row["name"],
            price=Decimal(row["price"]),
            capacity=row["capacity"],
            remaining_capacity=row["remaining_capacity"],
            status=TicketStatus(row["status"]),
        )


class RegistrationRepository:
    """报名和候补仓储。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, registration: Registration) -> Registration:
        self.database.execute(
            "INSERT INTO registrations(id, user_id, activity_id, session_id, "
            "ticket_type_id, status, request_id, ticket_code, activity_snapshot, "
            "session_snapshot, ticket_snapshot, created_at, cancelled_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                registration.id,
                registration.user_id,
                registration.activity_id,
                registration.session_id,
                registration.ticket_type_id,
                registration.status.value,
                registration.request_id,
                registration.ticket_code or None,
                snapshot_to_text(registration.activity_snapshot),
                snapshot_to_text(registration.session_snapshot),
                snapshot_to_text(registration.ticket_snapshot),
                dt_to_text(registration.created_at),
                dt_to_text(registration.cancelled_at),
            ),
        )
        self.database.commit_if_needed()
        return registration

    def get(self, registration_id: int) -> Registration:
        return self._from_row(require_row(
            self.database.query_one(
                "SELECT * FROM registrations WHERE id = ?", (registration_id,)
            ),
            "报名记录",
        ))

    def by_request_id(self, request_id: str) -> Registration | None:
        row = self.database.query_one(
            "SELECT * FROM registrations WHERE request_id = ?", (request_id,)
        )
        return self._from_row(row) if row else None

    def by_ticket_code(self, ticket_code: str) -> Registration | None:
        row = self.database.query_one(
            "SELECT * FROM registrations WHERE ticket_code = ?", (ticket_code,)
        )
        return self._from_row(row) if row else None

    def update(self, registration: Registration) -> Registration:
        self.database.execute(
            "UPDATE registrations SET status = ?, ticket_code = ?, cancelled_at = ? "
            "WHERE id = ?",
            (
                registration.status.value,
                registration.ticket_code or None,
                dt_to_text(registration.cancelled_at),
                registration.id,
            ),
        )
        self.database.commit_if_needed()
        return registration

    def list_by_user(self, user_id: int) -> list[Registration]:
        rows = self.database.query_all(
            "SELECT * FROM registrations WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        return [self._from_row(row) for row in rows]

    def list_by_session(
        self, session_id: int, status: RegistrationStatus | None = None
    ) -> list[Registration]:
        if status is None:
            rows = self.database.query_all(
                "SELECT * FROM registrations WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            )
        else:
            rows = self.database.query_all(
                "SELECT * FROM registrations WHERE session_id = ? AND status = ? "
                "ORDER BY created_at",
                (session_id, status.value),
            )
        return [self._from_row(row) for row in rows]

    def add_waitlist_entry(self, entry: WaitlistEntry) -> WaitlistEntry:
        self.database.execute(
            "INSERT INTO waitlist_entries(id, registration_id, position, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                entry.id,
                entry.registration_id,
                entry.position,
                dt_to_text(entry.created_at),
            ),
        )
        self.database.commit_if_needed()
        return entry

    def next_waitlist(self, session_id: int) -> Registration | None:
        row = self.database.query_one(
            "SELECT r.* FROM registrations r JOIN waitlist_entries w "
            "ON r.id = w.registration_id WHERE r.session_id = ? "
            "AND r.status = ? ORDER BY w.position, w.created_at LIMIT 1",
            (session_id, RegistrationStatus.WAITLISTED.value),
        )
        return self._from_row(row) if row else None

    def waitlist_position(self, session_id: int) -> int:
        row = self.database.query_one(
            "SELECT COALESCE(MAX(w.position), 0) + 1 AS next_position "
            "FROM waitlist_entries w JOIN registrations r "
            "ON r.id = w.registration_id WHERE r.session_id = ?",
            (session_id,),
        )
        return int(row["next_position"])

    def remove_waitlist_entry(self, registration_id: int) -> None:
        self.database.execute(
            "DELETE FROM waitlist_entries WHERE registration_id = ?", (registration_id,)
        )
        self.database.commit_if_needed()

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Registration:
        return Registration(
            id=row["id"],
            user_id=row["user_id"],
            activity_id=row["activity_id"],
            session_id=row["session_id"],
            ticket_type_id=row["ticket_type_id"],
            status=RegistrationStatus(row["status"]),
            request_id=row["request_id"],
            ticket_code=row["ticket_code"] or "",
            activity_snapshot=snapshot_from_text(row["activity_snapshot"]),
            session_snapshot=snapshot_from_text(row["session_snapshot"]),
            ticket_snapshot=snapshot_from_text(row["ticket_snapshot"]),
            created_at=text_to_dt(row["created_at"]),
            cancelled_at=text_to_dt(row["cancelled_at"]),
        )


class CheckInRepository:
    """签到仓储。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, check_in: CheckIn) -> CheckIn:
        self.database.execute(
            "INSERT INTO checkins(id, registration_id, checker_id, checked_at, method) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                check_in.id,
                check_in.registration_id,
                check_in.checker_id,
                dt_to_text(check_in.checked_at),
                check_in.method.value,
            ),
        )
        self.database.commit_if_needed()
        return check_in

    def by_registration(self, registration_id: int) -> CheckIn | None:
        row = self.database.query_one(
            "SELECT * FROM checkins WHERE registration_id = ?", (registration_id,)
        )
        if row is None:
            return None
        return CheckIn(
            id=row["id"],
            registration_id=row["registration_id"],
            checker_id=row["checker_id"],
            checked_at=text_to_dt(row["checked_at"]),
            method=CheckInMethod(row["method"]),
        )


class NotificationRepository:
    """通知仓储。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, notification: Notification) -> Notification:
        self.database.execute(
            "INSERT INTO notifications(id, user_id, title, content, activity_id, "
            "registration_id, sent_at, read_at, status, retry_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                notification.id,
                notification.user_id,
                notification.title,
                notification.content,
                notification.activity_id,
                notification.registration_id,
                dt_to_text(notification.sent_at),
                dt_to_text(notification.read_at),
                notification.status.value,
                notification.retry_count,
            ),
        )
        self.database.commit_if_needed()
        return notification

    def update(self, notification: Notification) -> Notification:
        self.database.execute(
            "UPDATE notifications SET sent_at = ?, read_at = ?, status = ?, "
            "retry_count = ? WHERE id = ?",
            (
                dt_to_text(notification.sent_at),
                dt_to_text(notification.read_at),
                notification.status.value,
                notification.retry_count,
                notification.id,
            ),
        )
        self.database.commit_if_needed()
        return notification

    def list_by_user(self, user_id: int) -> list[Notification]:
        rows = self.database.query_all(
            "SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC", (user_id,)
        )
        return [
            Notification(
                id=row["id"],
                user_id=row["user_id"],
                title=row["title"],
                content=row["content"],
                activity_id=row["activity_id"],
                registration_id=row["registration_id"],
                sent_at=text_to_dt(row["sent_at"]),
                read_at=text_to_dt(row["read_at"]),
                status=NotificationStatus(row["status"]),
                retry_count=row["retry_count"],
            )
            for row in rows
        ]


class AuditLogRepository:
    """审计日志仓储。"""

    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, audit_log: AuditLog) -> AuditLog:
        self.database.execute(
            "INSERT INTO audit_logs(id, operator_id, action, before_state, "
            "after_state, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                audit_log.id,
                audit_log.operator_id,
                audit_log.action,
                audit_log.before_state,
                audit_log.after_state,
                dt_to_text(audit_log.created_at),
            ),
        )
        self.database.commit_if_needed()
        return audit_log

    def list_recent(self, limit: int = 100) -> list[AuditLog]:
        rows = self.database.query_all(
            "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [
            AuditLog(
                id=row["id"],
                operator_id=row["operator_id"],
                action=row["action"],
                before_state=row["before_state"],
                after_state=row["after_state"],
                created_at=text_to_dt(row["created_at"]),
            )
            for row in rows
        ]


@dataclass(slots=True)
class RepositoryBundle:
    """将所有仓储绑定到同一个数据库。"""

    database: Database
    users: UserRepository = field(init=False)
    activities: ActivityRepository = field(init=False)
    sessions: SessionRepository = field(init=False)
    tickets: TicketTypeRepository = field(init=False)
    registrations: RegistrationRepository = field(init=False)
    checkins: CheckInRepository = field(init=False)
    notifications: NotificationRepository = field(init=False)
    audit_logs: AuditLogRepository = field(init=False)

    def __post_init__(self) -> None:
        self.database.initialize()
        self.users = UserRepository(self.database)
        self.activities = ActivityRepository(self.database)
        self.sessions = SessionRepository(self.database)
        self.tickets = TicketTypeRepository(self.database)
        self.registrations = RegistrationRepository(self.database)
        self.checkins = CheckInRepository(self.database)
        self.notifications = NotificationRepository(self.database)
        self.audit_logs = AuditLogRepository(self.database)

"""与实验二 UML 类图对应的领域对象。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from .enums import (
    ActivityStatus,
    CheckInMethod,
    NotificationStatus,
    RegistrationStatus,
    Role,
    SessionStatus,
    TicketStatus,
)
from .exceptions import CapacityError, ValidationError


def utc_now() -> datetime:
    """返回无时区的 UTC 时间，便于 SQLite 保存和比较。"""

    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def new_id() -> int:
    """生成可用于本地数据库的正整数标识。"""

    return uuid4().int % 2_000_000_000


@dataclass(slots=True)
class Snapshot:
    """报名时保存的不可变业务快照。"""

    title: str
    name: str
    price: Decimal = Decimal("0")
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """转换为可序列化字典。"""

        return {
            "title": self.title,
            "name": self.name,
            "price": str(self.price),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class User:
    """系统用户。"""

    id: int
    name: str
    roles: set[Role] = field(default_factory=lambda: {Role.PARTICIPANT})
    username: str = ""
    password_hash: str = ""
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("用户姓名不能为空")
        if not self.username:
            self.username = f"user-{self.id}"
        self.roles = {Role(role) for role in self.roles}

    def has_role(self, role: Role) -> bool:
        """判断用户是否具有指定角色。"""

        return role in self.roles or Role.ADMIN in self.roles

    def add_role(self, role: Role) -> None:
        """授予用户角色。"""

        self.roles.add(Role(role))

    def remove_role(self, role: Role) -> None:
        """移除用户角色，但不允许移除最后一个角色。"""

        if len(self.roles) == 1:
            raise ValidationError("用户至少需要保留一个角色")
        self.roles.discard(Role(role))


@dataclass(slots=True)
class Activity:
    """活动聚合根。"""

    id: int
    title: str
    organizer_id: int
    description: str = ""
    location: str = ""
    status: ActivityStatus = ActivityStatus.DRAFT
    report_reason: str = ""
    created_at: datetime = field(default_factory=utc_now)
    sessions: list["Session"] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.title.strip()) < 2:
            raise ValidationError("活动标题至少需要两个字符")
        if self.organizer_id <= 0:
            raise ValidationError("组织者标识必须为正数")

    def submit_review(self) -> None:
        """提交审核。"""

        if self.status not in {ActivityStatus.DRAFT, ActivityStatus.REJECTED}:
            raise ValidationError("当前状态不能提交审核")
        self.status = ActivityStatus.PENDING_REVIEW
        self.report_reason = ""

    def publish(self) -> None:
        """审核通过后发布活动。"""

        if self.status != ActivityStatus.PENDING_REVIEW:
            raise ValidationError("只有待审核活动可以发布")
        if not self.sessions:
            raise ValidationError("活动至少需要一个场次")
        self.status = ActivityStatus.PUBLISHED

    def reject(self, reason: str) -> None:
        """驳回活动并记录原因。"""

        if self.status != ActivityStatus.PENDING_REVIEW:
            raise ValidationError("只有待审核活动可以驳回")
        if not reason.strip():
            raise ValidationError("驳回原因不能为空")
        self.status = ActivityStatus.REJECTED
        self.report_reason = reason.strip()

    def close(self) -> None:
        """关闭活动。"""

        if self.status != ActivityStatus.PUBLISHED:
            raise ValidationError("只有已发布活动可以关闭")
        self.status = ActivityStatus.CLOSED

    def add_session(self, session: "Session") -> None:
        """为活动增加场次。"""

        if session.activity_id != self.id:
            raise ValidationError("场次不属于当前活动")
        if self.status not in {ActivityStatus.DRAFT, ActivityStatus.REJECTED}:
            raise ValidationError("活动发布后不能新增场次")
        self.sessions.append(session)


@dataclass(slots=True)
class Session:
    """活动场次。"""

    id: int
    activity_id: int
    start_at: datetime
    end_at: datetime
    capacity: int
    status: SessionStatus = SessionStatus.DRAFT
    remaining_capacity: int | None = None
    ticket_types: list["TicketType"] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.end_at <= self.start_at:
            raise ValidationError("场次结束时间必须晚于开始时间")
        if self.capacity <= 0:
            raise CapacityError("场次容量必须大于零")
        if self.remaining_capacity is None:
            self.remaining_capacity = self.capacity
        if not 0 <= self.remaining_capacity <= self.capacity:
            raise CapacityError("场次剩余容量超出范围")

    def open(self) -> None:
        """开放场次报名。"""

        if self.status not in {SessionStatus.DRAFT, SessionStatus.FULL}:
            raise ValidationError("当前场次不能开放")
        if self.remaining_capacity == 0:
            self.status = SessionStatus.FULL
            raise CapacityError("场次没有剩余容量")
        self.status = SessionStatus.OPEN

    def reserve(self) -> None:
        """占用一个场次名额。"""

        if self.remaining_capacity is None or self.remaining_capacity <= 0:
            self.status = SessionStatus.FULL
            raise CapacityError("场次已满")
        self.remaining_capacity -= 1
        self.status = SessionStatus.OPEN if self.remaining_capacity else SessionStatus.FULL

    def release(self) -> None:
        """释放一个场次名额。"""

        if self.remaining_capacity is None or self.remaining_capacity >= self.capacity:
            raise CapacityError("场次剩余容量不能超过总容量")
        self.remaining_capacity += 1
        self.status = SessionStatus.OPEN

    def close(self) -> None:
        """关闭报名。"""

        if self.status not in {SessionStatus.OPEN, SessionStatus.FULL}:
            raise ValidationError("当前场次不能关闭")
        self.status = SessionStatus.CLOSED


@dataclass(slots=True)
class TicketType:
    """场次中的票种。"""

    id: int
    session_id: int
    name: str
    price: Decimal
    capacity: int
    status: TicketStatus = TicketStatus.ACTIVE
    remaining_capacity: int | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("票种名称不能为空")
        if self.price < Decimal("0"):
            raise ValidationError("票价不能为负数")
        if self.capacity <= 0:
            raise CapacityError("票种容量必须大于零")
        if self.remaining_capacity is None:
            self.remaining_capacity = self.capacity
        if not 0 <= self.remaining_capacity <= self.capacity:
            raise CapacityError("票种剩余容量超出范围")

    def reserve(self) -> None:
        """占用一个票种名额。"""

        if self.remaining_capacity is None or self.remaining_capacity <= 0:
            self.status = TicketStatus.SOLD_OUT
            raise CapacityError("票种已售罄")
        self.remaining_capacity -= 1
        if self.remaining_capacity == 0:
            self.status = TicketStatus.SOLD_OUT

    def release(self) -> None:
        """释放一个票种名额。"""

        if self.remaining_capacity is None or self.remaining_capacity >= self.capacity:
            raise CapacityError("票种剩余容量不能超过总容量")
        self.remaining_capacity += 1
        self.status = TicketStatus.ACTIVE


@dataclass(slots=True)
class Registration:
    """参与者报名记录。"""

    id: int
    user_id: int
    activity_id: int
    session_id: int
    ticket_type_id: int
    status: RegistrationStatus
    request_id: str
    ticket_code: str = ""
    activity_snapshot: Snapshot | None = None
    session_snapshot: Snapshot | None = None
    ticket_snapshot: Snapshot | None = None
    created_at: datetime = field(default_factory=utc_now)
    cancelled_at: datetime | None = None

    @classmethod
    def create(
        cls,
        user_id: int,
        activity_id: int,
        session_id: int,
        ticket_type_id: int,
        request_id: str,
        activity_snapshot: Snapshot,
        session_snapshot: Snapshot,
        ticket_snapshot: Snapshot,
    ) -> "Registration":
        """创建已报名记录并生成票码。"""

        if not request_id.strip():
            raise ValidationError("requestId 不能为空")
        return cls(
            id=new_id(),
            user_id=user_id,
            activity_id=activity_id,
            session_id=session_id,
            ticket_type_id=ticket_type_id,
            status=RegistrationStatus.REGISTERED,
            request_id=request_id,
            ticket_code=f"T-{uuid4().hex[:12].upper()}",
            activity_snapshot=activity_snapshot,
            session_snapshot=session_snapshot,
            ticket_snapshot=ticket_snapshot,
        )

    @classmethod
    def create_waitlist(
        cls,
        user_id: int,
        activity_id: int,
        session_id: int,
        ticket_type_id: int,
        request_id: str,
        activity_snapshot: Snapshot,
        session_snapshot: Snapshot,
        ticket_snapshot: Snapshot,
    ) -> "Registration":
        """创建候补记录。"""

        if not request_id.strip():
            raise ValidationError("requestId 不能为空")
        return cls(
            id=new_id(),
            user_id=user_id,
            activity_id=activity_id,
            session_id=session_id,
            ticket_type_id=ticket_type_id,
            status=RegistrationStatus.WAITLISTED,
            request_id=request_id,
            activity_snapshot=activity_snapshot,
            session_snapshot=session_snapshot,
            ticket_snapshot=ticket_snapshot,
        )

    def cancel(self) -> None:
        """取消报名或候补。"""

        if self.status not in {
            RegistrationStatus.REGISTERED,
            RegistrationStatus.WAITLISTED,
        }:
            raise ValidationError("当前报名状态不能取消")
        self.status = RegistrationStatus.CANCELLED
        self.cancelled_at = utc_now()

    def promote(self) -> None:
        """将候补记录递补为已报名。"""

        if self.status != RegistrationStatus.WAITLISTED:
            raise ValidationError("只有候补记录可以递补")
        self.status = RegistrationStatus.REGISTERED
        self.ticket_code = f"T-{uuid4().hex[:12].upper()}"

    def mark_checked_in(self) -> None:
        """标记为已签到。"""

        if self.status != RegistrationStatus.REGISTERED:
            raise ValidationError("只有已报名记录可以签到")
        self.status = RegistrationStatus.CHECKED_IN

    def mark_absent(self) -> None:
        """标记为缺席。"""

        if self.status != RegistrationStatus.REGISTERED:
            raise ValidationError("只有未签到的已报名记录可以标记缺席")
        self.status = RegistrationStatus.ABSENT


@dataclass(slots=True)
class WaitlistEntry:
    """候补队列中的排序信息。"""

    id: int
    registration_id: int
    position: int
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class CheckIn:
    """签到记录。"""

    id: int
    registration_id: int
    checker_id: int
    checked_at: datetime = field(default_factory=utc_now)
    method: CheckInMethod = CheckInMethod.MANUAL

    def verify(self) -> bool:
        """验证签到记录是否具备最小有效信息。"""

        return self.registration_id > 0 and self.checker_id > 0


@dataclass(slots=True)
class AuditLog:
    """操作审计日志。"""

    id: int
    operator_id: int
    action: str
    before_state: str
    after_state: str
    created_at: datetime = field(default_factory=utc_now)

    def record(self) -> dict[str, str | int]:
        """返回适合持久化的日志记录。"""

        return {
            "id": self.id,
            "operator_id": self.operator_id,
            "action": self.action,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "created_at": self.created_at.isoformat(sep=" "),
        }


@dataclass(slots=True)
class Notification:
    """站内通知。"""

    id: int
    user_id: int
    title: str
    content: str
    activity_id: int | None = None
    registration_id: int | None = None
    sent_at: datetime | None = None
    read_at: datetime | None = None
    status: NotificationStatus = NotificationStatus.PENDING
    retry_count: int = 0

    def mark_sent(self) -> None:
        """标记通知发送成功。"""

        self.sent_at = utc_now()
        self.status = NotificationStatus.SENT

    def mark_read(self) -> None:
        """将通知标记为已读。"""

        if self.status not in {NotificationStatus.SENT, NotificationStatus.READ}:
            raise ValidationError("通知尚未发送，不能标记为已读")
        self.read_at = utc_now()
        self.status = NotificationStatus.READ

    def retry(self) -> None:
        """增加重试次数并回到待发送状态。"""

        if self.status != NotificationStatus.FAILED:
            raise ValidationError("只有失败通知可以重试")
        self.retry_count += 1
        self.status = NotificationStatus.PENDING

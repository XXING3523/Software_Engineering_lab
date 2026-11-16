"""系统使用的状态和角色枚举。"""

from enum import Enum


class Role(str, Enum):
    """用户角色。"""

    PARTICIPANT = "participant"
    ORGANIZER = "organizer"
    CHECKER = "checker"
    ADMIN = "admin"


class ActivityStatus(str, Enum):
    """活动审核与发布状态。"""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"
    PUBLISHED = "published"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class SessionStatus(str, Enum):
    """场次状态。"""

    DRAFT = "draft"
    OPEN = "open"
    FULL = "full"
    CLOSED = "closed"
    FINISHED = "finished"


class TicketStatus(str, Enum):
    """票种状态。"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SOLD_OUT = "sold_out"


class RegistrationStatus(str, Enum):
    """报名状态机中的状态。"""

    REGISTERED = "registered"
    WAITLISTED = "waitlisted"
    CANCELLED = "cancelled"
    CHECKED_IN = "checked_in"
    ABSENT = "absent"
    EXPIRED = "expired"


class CheckInMethod(str, Enum):
    """签到方式。"""

    QR_CODE = "qr_code"
    MANUAL = "manual"


class NotificationStatus(str, Enum):
    """通知发送状态。"""

    PENDING = "pending"
    SENT = "sent"
    READ = "read"
    FAILED = "failed"

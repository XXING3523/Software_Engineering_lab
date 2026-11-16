"""报名状态机。"""

from __future__ import annotations

from .enums import RegistrationStatus
from .exceptions import InvalidTransitionError


ALLOWED_REGISTRATION_TRANSITIONS: dict[
    RegistrationStatus, frozenset[RegistrationStatus]
] = {
    RegistrationStatus.REGISTERED: frozenset(
        {
            RegistrationStatus.CANCELLED,
            RegistrationStatus.CHECKED_IN,
            RegistrationStatus.ABSENT,
        }
    ),
    RegistrationStatus.WAITLISTED: frozenset(
        {RegistrationStatus.REGISTERED, RegistrationStatus.CANCELLED, RegistrationStatus.EXPIRED}
    ),
    RegistrationStatus.CHECKED_IN: frozenset({RegistrationStatus.REGISTERED}),
    RegistrationStatus.ABSENT: frozenset({RegistrationStatus.CHECKED_IN}),
    RegistrationStatus.CANCELLED: frozenset(),
    RegistrationStatus.EXPIRED: frozenset(),
}


def can_transition(
    current: RegistrationStatus, target: RegistrationStatus
) -> bool:
    """判断状态转换是否合法。"""

    return target in ALLOWED_REGISTRATION_TRANSITIONS.get(current, frozenset())


def transition(
    current: RegistrationStatus, target: RegistrationStatus
) -> RegistrationStatus:
    """执行一次状态转换，不允许绕过状态机。"""

    if not can_transition(current, target):
        raise InvalidTransitionError(f"不允许从 {current.value} 转换到 {target.value}")
    return target

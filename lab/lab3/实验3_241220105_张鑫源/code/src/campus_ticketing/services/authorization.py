"""角色权限检查。"""

from campus_ticketing.domain.entities import User
from campus_ticketing.domain.enums import Role
from campus_ticketing.domain.exceptions import PermissionDeniedError


def require_role(user: User, role: Role) -> None:
    """要求当前用户具有指定角色。"""

    if not user.enabled or not user.has_role(role):
        raise PermissionDeniedError(f"用户 {user.name} 缺少角色 {role.value}")


def require_any_role(user: User, *roles: Role) -> None:
    """要求当前用户至少具有一个角色。"""

    if not user.enabled or not any(user.has_role(role) for role in roles):
        allowed = ", ".join(role.value for role in roles)
        raise PermissionDeniedError(f"用户 {user.name} 需要角色：{allowed}")

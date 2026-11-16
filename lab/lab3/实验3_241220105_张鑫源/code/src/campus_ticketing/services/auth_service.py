"""用户注册和登录服务。"""

from __future__ import annotations

import hashlib

from campus_ticketing.domain.entities import User, new_id
from campus_ticketing.domain.enums import Role
from campus_ticketing.domain.exceptions import ValidationError
from campus_ticketing.repositories import RepositoryBundle


class AuthService:
    """处理用户账号和角色。"""

    def __init__(self, repositories: RepositoryBundle) -> None:
        self.repositories = repositories

    def register(
        self,
        username: str,
        name: str,
        password: str,
        roles: set[Role] | None = None,
    ) -> User:
        """注册用户。"""

        if len(username.strip()) < 3:
            raise ValidationError("用户名至少需要三个字符")
        if len(password) < 4:
            raise ValidationError("密码至少需要四个字符")
        if self.repositories.users.by_username(username):
            raise ValidationError("用户名已经存在")
        user = User(
            id=new_id(),
            username=username.strip(),
            name=name.strip(),
            roles=roles or {Role.PARTICIPANT},
            password_hash=self._hash(password),
        )
        return self.repositories.users.add(user)

    def login(self, username: str, password: str) -> User:
        """校验账号密码并返回用户。"""

        user = self.repositories.users.by_username(username.strip())
        if user is None or not user.enabled:
            raise ValidationError("用户名或密码错误")
        if user.password_hash != self._hash(password):
            raise ValidationError("用户名或密码错误")
        return user

    def ensure_demo_users(self) -> list[User]:
        """初始化四类演示账号，重复调用不会重复创建。"""

        demos = [
            ("participant", "参与者", {Role.PARTICIPANT}),
            ("organizer", "组织者", {Role.ORGANIZER}),
            ("checker", "检票人员", {Role.CHECKER}),
            ("admin", "管理员", {Role.ADMIN}),
        ]
        users: list[User] = []
        for username, name, roles in demos:
            existing = self.repositories.users.by_username(username)
            users.append(existing or self.register(username, name, "1234", roles))
        return users

    @staticmethod
    def _hash(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

"""审计日志服务。"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass

from campus_ticketing.domain.entities import AuditLog, User, new_id
from campus_ticketing.repositories import RepositoryBundle


class AuditService:
    """记录业务对象变化。"""

    def __init__(self, repositories: RepositoryBundle) -> None:
        self.repositories = repositories

    def record(
        self,
        operator: User,
        action: str,
        before: object,
        after: object,
    ) -> AuditLog:
        """保存一条结构化审计日志。"""

        audit_log = AuditLog(
            id=new_id(),
            operator_id=operator.id,
            action=action,
            before_state=self._serialize(before),
            after_state=self._serialize(after),
        )
        return self.repositories.audit_logs.add(audit_log)

    def recent(self, limit: int = 100) -> list[AuditLog]:
        """查看最近日志。"""

        return self.repositories.audit_logs.list_recent(limit)

    @staticmethod
    def _serialize(value: object) -> str:
        if isinstance(value, str):
            return value
        if is_dataclass(value):
            return json.dumps(asdict(value), default=str, ensure_ascii=False, sort_keys=True)
        return json.dumps(str(value), ensure_ascii=False)

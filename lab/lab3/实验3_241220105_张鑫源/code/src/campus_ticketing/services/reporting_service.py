"""统计、日志查询和报名导出服务。"""

from __future__ import annotations

import csv
from pathlib import Path

from campus_ticketing.domain.entities import User
from campus_ticketing.domain.enums import RegistrationStatus, Role
from campus_ticketing.domain.exceptions import PermissionDeniedError
from campus_ticketing.paths import EXPORT_DIR
from campus_ticketing.repositories import RepositoryBundle

from .authorization import require_role


class ReportingService:
    """为管理员和组织者提供报表。"""

    def __init__(self, repositories: RepositoryBundle) -> None:
        self.repositories = repositories

    def statistics(self, actor: User) -> dict[str, int]:
        """统计报名状态数量。"""

        require_role(actor, Role.ADMIN)
        rows = self.repositories.database.query_all(
            "SELECT status, COUNT(*) AS amount FROM registrations GROUP BY status"
        )
        result = {status.value: 0 for status in RegistrationStatus}
        result.update({row["status"]: row["amount"] for row in rows})
        result["activities"] = self._count("activities")
        result["users"] = self._count("users")
        return result

    def registrations_for_activity(
        self, actor: User, activity_id: int
    ) -> list[dict[str, object]]:
        """查看活动报名名单。"""

        activity = self.repositories.activities.get(activity_id)
        if not actor.has_role(Role.ADMIN) and activity.organizer_id != actor.id:
            raise PermissionDeniedError("只能查看自己组织的活动名单")
        rows = self.repositories.database.query_all(
            "SELECT r.id, u.name, u.username, r.status, r.ticket_code, r.created_at "
            "FROM registrations r JOIN users u ON r.user_id = u.id "
            "WHERE r.activity_id = ? ORDER BY r.created_at",
            (activity_id,),
        )
        return [dict(row) for row in rows]

    def export_registrations(
        self, actor: User, activity_id: int, target: Path | None = None
    ) -> Path:
        """导出活动报名名单。"""

        rows = self.registrations_for_activity(actor, activity_id)
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        output = target or EXPORT_DIR / f"registrations-{activity_id}.csv"
        with output.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["id", "name", "username", "status", "ticket_code", "created_at"],
            )
            writer.writeheader()
            writer.writerows(rows)
        return output

    def recent_audit(self, actor: User, limit: int = 100) -> list[dict[str, object]]:
        """返回管理员审计日志。"""

        require_role(actor, Role.ADMIN)
        return [
            {
                "id": log.id,
                "operator_id": log.operator_id,
                "action": log.action,
                "before_state": log.before_state,
                "after_state": log.after_state,
                "created_at": log.created_at,
            }
            for log in self.repositories.audit_logs.list_recent(limit)
        ]

    def _count(self, table: str) -> int:
        if table not in {"activities", "users"}:
            raise ValueError("不允许统计指定表")
        row = self.repositories.database.query_one(f"SELECT COUNT(*) AS amount FROM {table}")
        return int(row["amount"])

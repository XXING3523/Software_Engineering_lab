"""活动创建、审核、发布和查询服务。"""

from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from campus_ticketing.domain.entities import Activity, Session, TicketType, User, new_id
from campus_ticketing.domain.enums import ActivityStatus, Role, SessionStatus
from campus_ticketing.domain.exceptions import PermissionDeniedError, ValidationError
from campus_ticketing.paths import EXPORT_DIR
from campus_ticketing.repositories import RepositoryBundle

from .authorization import require_any_role, require_role
from .audit_service import AuditService


class ActivityService:
    """实现活动管理用例。"""

    def __init__(self, repositories: RepositoryBundle, audit: AuditService) -> None:
        self.repositories = repositories
        self.audit = audit

    def create_activity(
        self,
        actor: User,
        title: str,
        description: str,
        location: str,
    ) -> Activity:
        """组织者创建活动。"""

        require_any_role(actor, Role.ORGANIZER, Role.ADMIN)
        activity = Activity(
            id=new_id(),
            title=title.strip(),
            organizer_id=actor.id,
            description=description.strip(),
            location=location.strip(),
        )
        saved = self.repositories.activities.add(activity)
        self.audit.record(actor, "create_activity", None, saved)
        return saved

    def edit_activity(
        self,
        actor: User,
        activity_id: int,
        title: str,
        description: str,
        location: str,
    ) -> Activity:
        """编辑尚未发布的活动。"""

        activity = self._owned_activity(actor, activity_id)
        before = Activity(**self._activity_values(activity))
        if activity.status not in {ActivityStatus.DRAFT, ActivityStatus.REJECTED}:
            raise ValidationError("只有草稿或被驳回活动可以编辑")
        activity.title = title.strip()
        activity.description = description.strip()
        activity.location = location.strip()
        if len(activity.title) < 2:
            raise ValidationError("活动标题至少需要两个字符")
        saved = self.repositories.activities.update(activity)
        self.audit.record(actor, "edit_activity", before, saved)
        return saved

    def add_session(
        self,
        actor: User,
        activity_id: int,
        start_at: datetime,
        end_at: datetime,
        capacity: int,
    ) -> Session:
        """为活动增加场次。"""

        activity = self._owned_activity(actor, activity_id)
        session = Session(new_id(), activity.id, start_at, end_at, capacity)
        saved = self.repositories.sessions.add(session)
        self.audit.record(actor, "add_session", None, saved)
        return saved

    def add_ticket_type(
        self,
        actor: User,
        session_id: int,
        name: str,
        price: str,
        capacity: int,
    ) -> TicketType:
        """为场次增加票种。"""

        session = self.repositories.sessions.get(session_id)
        self._owned_activity(actor, session.activity_id)
        ticket = TicketType(new_id(), session.id, name, self._decimal(price), capacity)
        saved = self.repositories.tickets.add(ticket)
        self.audit.record(actor, "add_ticket_type", None, saved)
        return saved

    def submit_review(self, actor: User, activity_id: int) -> Activity:
        """组织者提交活动审核。"""

        activity = self._owned_activity(actor, activity_id)
        before = activity.status.value
        sessions = self.repositories.sessions.list_by_activity(activity_id)
        if not sessions:
            raise ValidationError("活动至少需要一个场次")
        activity.submit_review()
        saved = self.repositories.activities.update(activity)
        self.audit.record(actor, "submit_activity_review", before, saved.status.value)
        return saved

    def review_activity(
        self,
        actor: User,
        activity_id: int,
        approve: bool,
        reason: str = "",
    ) -> Activity:
        """管理员审核活动。"""

        require_role(actor, Role.ADMIN)
        activity = self.repositories.activities.get(activity_id)
        before = activity.status.value
        sessions = self.repositories.sessions.list_by_activity(activity_id)
        activity.sessions = sessions
        if approve:
            activity.publish()
            for session in sessions:
                if session.status == SessionStatus.DRAFT:
                    session.open()
                    self.repositories.sessions.update(session)
        else:
            activity.reject(reason)
        saved = self.repositories.activities.update(activity)
        self.audit.record(actor, "review_activity", before, saved.status.value)
        return saved

    def list_published(self, keyword: str = "") -> list[Activity]:
        """查询已发布活动。"""

        activities = self.repositories.activities.list_by_status(ActivityStatus.PUBLISHED)
        normalized = keyword.strip().lower()
        if not normalized:
            return activities
        return [
            activity
            for activity in activities
            if normalized in activity.title.lower()
            or normalized in activity.location.lower()
            or normalized in activity.description.lower()
        ]

    def details(self, activity_id: int) -> dict[str, object]:
        """查询活动、场次和票种的组合详情。"""

        activity = self.repositories.activities.get(activity_id)
        sessions: list[dict[str, object]] = []
        for session in self.repositories.sessions.list_by_activity(activity_id):
            tickets = self.repositories.tickets.list_by_session(session.id)
            sessions.append({"session": session, "tickets": tickets})
        return {"activity": activity, "sessions": sessions}

    def export_activities(self, target: Path | None = None) -> Path:
        """导出活动清单，供管理员留存。"""

        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        output = target or EXPORT_DIR / "activities.csv"
        activities = self.repositories.activities.list_by_status()
        with output.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream)
            writer.writerow(["id", "title", "organizer_id", "status", "location"])
            for activity in activities:
                writer.writerow(
                    [
                        activity.id,
                        activity.title,
                        activity.organizer_id,
                        activity.status.value,
                        activity.location,
                    ]
                )
        return output

    def _owned_activity(self, actor: User, activity_id: int) -> Activity:
        activity = self.repositories.activities.get(activity_id)
        if actor.has_role(Role.ADMIN):
            return activity
        require_role(actor, Role.ORGANIZER)
        if activity.organizer_id != actor.id:
            raise PermissionDeniedError("只能操作自己创建的活动")
        return activity

    @staticmethod
    def _decimal(value: str) -> Decimal:
        return Decimal(value)

    @staticmethod
    def _activity_values(activity: Activity) -> dict[str, object]:
        return {
            "id": activity.id,
            "title": activity.title,
            "organizer_id": activity.organizer_id,
            "description": activity.description,
            "location": activity.location,
            "status": activity.status,
            "report_reason": activity.report_reason,
            "created_at": activity.created_at,
            "sessions": list(activity.sessions),
        }

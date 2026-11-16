"""应用装配、演示数据和生命周期管理。"""

from __future__ import annotations

from datetime import datetime, timedelta

from campus_ticketing.domain.enums import ActivityStatus, Role
from campus_ticketing.paths import DATABASE_PATH, ensure_runtime_directories
from campus_ticketing.repositories import Database, RepositoryBundle
from campus_ticketing.scheduler import SchedulerService
from campus_ticketing.services import (
    ActivityService,
    AuditService,
    AuthService,
    CheckInService,
    NotificationService,
    RegistrationService,
    ReportingService,
)


class Application:
    """创建并持有系统所有服务。"""

    def __init__(self, database_path: str | None = None) -> None:
        ensure_runtime_directories()
        self.database = Database(database_path or DATABASE_PATH)
        self.repositories = RepositoryBundle(self.database)
        self.auth = AuthService(self.repositories)
        self.audit = AuditService(self.repositories)
        self.notifications = NotificationService(self.repositories)
        self.activities = ActivityService(self.repositories, self.audit)
        self.registrations = RegistrationService(
            self.repositories, self.notifications, self.audit
        )
        self.checkins = CheckInService(
            self.repositories, self.notifications, self.audit
        )
        self.reporting = ReportingService(self.repositories)
        self.scheduler = SchedulerService(
            self.repositories, self.notifications, self.audit
        )
        self.users = self.auth.ensure_demo_users()
        self.seed_demo_activity()

    def seed_demo_activity(self) -> None:
        """首次启动时创建一个可供演示的已发布活动。"""

        if self.repositories.activities.list_by_status(ActivityStatus.PUBLISHED):
            return
        organizer = next(user for user in self.users if user.has_role(Role.ORGANIZER))
        admin = next(user for user in self.users if user.has_role(Role.ADMIN))
        activity = self.activities.create_activity(
            organizer,
            "校园活动票务系统演示",
            "用于演示查询、报名、候补、签到和通知流程。",
            "软件工程实验室",
        )
        start = datetime.now().replace(microsecond=0) + timedelta(days=1)
        session = self.activities.add_session(
            organizer, activity.id, start, start + timedelta(hours=2), 5
        )
        self.activities.add_ticket_type(organizer, session.id, "普通票", "0", 5)
        self.activities.submit_review(organizer, activity.id)
        self.activities.review_activity(admin, activity.id, True)

    def close(self) -> None:
        """关闭数据库连接。"""

        self.database.close()

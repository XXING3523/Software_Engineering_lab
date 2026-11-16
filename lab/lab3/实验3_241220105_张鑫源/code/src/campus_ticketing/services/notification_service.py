"""站内通知服务。"""

from __future__ import annotations

from campus_ticketing.domain.entities import Notification, User, new_id
from campus_ticketing.domain.enums import NotificationStatus
from campus_ticketing.repositories import RepositoryBundle


class NotificationService:
    """创建、发送、阅读和重试通知。"""

    def __init__(self, repositories: RepositoryBundle) -> None:
        self.repositories = repositories

    def send(
        self,
        user_id: int,
        title: str,
        content: str,
        activity_id: int | None = None,
        registration_id: int | None = None,
    ) -> Notification:
        """创建一条已发送的站内通知。"""

        notification = Notification(
            id=new_id(),
            user_id=user_id,
            title=title,
            content=content,
            activity_id=activity_id,
            registration_id=registration_id,
        )
        notification.mark_sent()
        return self.repositories.notifications.add(notification)

    def list_for_user(self, user: User) -> list[Notification]:
        """读取用户通知。"""

        return self.repositories.notifications.list_by_user(user.id)

    def mark_read(self, user: User, notification_id: int) -> Notification:
        """将属于当前用户的通知标记为已读。"""

        notifications = self.repositories.notifications.list_by_user(user.id)
        notification = next(
            (item for item in notifications if item.id == notification_id), None
        )
        if notification is None:
            raise ValueError("通知不存在或不属于当前用户")
        notification.mark_read()
        return self.repositories.notifications.update(notification)

    def retry_failed(self, notification_id: int) -> Notification:
        """重试失败通知。"""

        rows = self.repositories.database.query_all(
            "SELECT * FROM notifications WHERE id = ?", (notification_id,)
        )
        if not rows:
            raise ValueError("通知不存在")
        row = rows[0]
        notification = Notification(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            content=row["content"],
            activity_id=row["activity_id"],
            registration_id=row["registration_id"],
            status=NotificationStatus(row["status"]),
            retry_count=row["retry_count"],
        )
        notification.retry()
        notification.mark_sent()
        return self.repositories.notifications.update(notification)

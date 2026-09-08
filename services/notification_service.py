import uuid
from typing import List, Optional

from extensions import db
from models.notification import Notification


class NotificationService:
    @staticmethod
    def list_notifications() -> List[Notification]:
        return (
            db.session.query(Notification)
            .filter(Notification.deleted_at.is_(None))
            .order_by(Notification.created_at.desc())
            .all()
        )

    @staticmethod
    def create_notification(message: str, created_by: Optional[uuid.UUID]) -> Notification:
        notification = Notification(message=message, created_by=created_by)
        notification.save()
        Notification.commit()
        return notification

    @staticmethod
    def delete_notification(notification_id: uuid.UUID) -> bool:
        notification = Notification.get(notification_id)
        if not notification or notification.deleted_at is not None:
            return False
        notification.soft_delete()
        Notification.commit()
        return True

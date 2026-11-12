import uuid
from typing import Optional

from models.feedback import Feedback


class FeedbackService:
    MAX_CONTENT_LENGTH = 2000
    MAX_PAGE_URL_LENGTH = 500

    @staticmethod
    def create_feedback(
        user_id: uuid.UUID, role: str, content: str, page_url: Optional[str]
    ) -> Feedback:
        feedback = Feedback(
            user_id=user_id,
            role=role,
            content=content,
            page_url=(page_url or None) and page_url[:FeedbackService.MAX_PAGE_URL_LENGTH],
        )
        feedback.save()
        Feedback.commit()
        return feedback

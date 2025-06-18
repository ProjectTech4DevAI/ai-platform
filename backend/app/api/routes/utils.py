import logging
from fastapi import APIRouter, Depends
from pydantic.networks import EmailStr

from app.api.deps import get_current_active_superuser
from app.models import Message
from app.utils import generate_test_email, send_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
    include_in_schema=False,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    logger.info(f"[utils.test_email] Sending test email | email_to={email_to}")
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    logger.info(f"[utils.test_email] Test email sent successfully | email_to={email_to}")
    return Message(message="Test email sent")


@router.get("/health/", include_in_schema=False)
async def health_check() -> bool:
    logger.debug("[utils.health_check] Health check OK")
    return True

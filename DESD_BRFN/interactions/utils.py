"""Helpers for recording user interactions without blocking the request."""
import logging
from .models import UserInteraction

logger = logging.getLogger(__name__)


def log_interaction(request, interaction_type, product=None, metadata=None):
    """
    Fire-and-forget interaction log. Silently swallows errors so a logging
    failure never breaks the calling view.
    """
    try:
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key or ''
        UserInteraction.objects.create(
            user=user,
            session_key=session_key,
            interaction_type=interaction_type,
            product=product,
            metadata=metadata or {},
        )
    except Exception as e:
        logger.warning("Failed to log interaction (%s): %s", interaction_type, e)

"""
Config package. Re-export settings for convenience:

    from config import settings
    from config import SKILLS_TAXONOMY_PATH
"""

from . import settings  # noqa: F401
from .settings import (  # noqa: F401
    PROJECT_ROOT,
    CONFIG_DIR,
    DATA_DIR,
    RESUME_DIR,
    JD_DIR,
    PROCESSED_DIR,
    LABELED_DIR,
    SKILLS_TAXONOMY_PATH,
    SCORE_WEIGHTS,
    SIMILARITY_METHOD,
    REVIEW_BADGE_THRESHOLD,
    ENABLE_AUTO_REJECT,
)

__all__ = [
    "settings",
    "PROJECT_ROOT",
    "CONFIG_DIR",
    "DATA_DIR",
    "RESUME_DIR",
    "JD_DIR",
    "PROCESSED_DIR",
    "LABELED_DIR",
    "SKILLS_TAXONOMY_PATH",
    "SCORE_WEIGHTS",
    "SIMILARITY_METHOD",
    "REVIEW_BADGE_THRESHOLD",
    "ENABLE_AUTO_REJECT",
]
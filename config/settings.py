"""
Central configuration. Every tunable lives here, not scattered in code.

Rule: if you want to change scoring behavior, change THIS FILE — never
the algorithm files in src/scoring/.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
RESUME_DIR = DATA_DIR / "resumes"
JD_DIR = DATA_DIR / "job_descriptions"
PROCESSED_DIR = DATA_DIR / "processed"
LABELED_DIR = DATA_DIR / "labeled"

SKILLS_TAXONOMY_PATH = CONFIG_DIR / "skills.json"

# ---------------------------------------------------------------------------
# Scoring weights — MUST sum to 1.0
# ---------------------------------------------------------------------------
SCORE_WEIGHTS: dict[str, float] = {
    "keyword":    0.50,   # skill overlap (highest weight — most aligned with recruiter intent)
    "similarity": 0.25,   # TF-IDF or semantic similarity to JD
    "experience": 0.25,   # years vs. JD's stated requirement
}

# If the JD doesn't state a years requirement, redistribute experience's
# weight proportionally to the others. Set to False to always cap
# experience at its weight (penalizing candidates when JD is silent).
REDISTRIBUTE_MISSING_EXPERIENCE = True

# ---------------------------------------------------------------------------
# Keyword score tuning
# ---------------------------------------------------------------------------
# If a candidate has NONE of the required skills, score is 0 regardless
# of resume length. Prevents a perfectly-written irrelevant resume from
# getting credit via similarity alone.
KEYWORD_ZERO_IF_NO_MATCH = True

# Optional: boost weight for skills mentioned in the JD's title/header.
# Set to 1.0 for no boost; 1.5 gives title-skills 50% more influence.
TITLE_SKILL_BOOST = 1.3

# ---------------------------------------------------------------------------
# Similarity score tuning
# ---------------------------------------------------------------------------
SIMILARITY_METHOD = "tfidf"       # "tfidf" | "semantic"
TFIDF_MIN_DF = 1                  # with few resumes, don't drop rare terms
TFIDF_MAX_FEATURES = 5000
TFIDF_NGRAM_RANGE = (1, 2)        # unigrams + bigrams

# Semantic model (only used if SIMILARITY_METHOD == "semantic")
SEMANTIC_MODEL_NAME = "all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Experience score tuning
# ---------------------------------------------------------------------------
# If candidate exceeds required years, cap contribution at this ratio.
# 1.0 = "10y and 5y get same score"; 1.2 = slight bonus for overqualification
EXPERIENCE_OVER_QUALIFIED_CAP = 1.0

# ---------------------------------------------------------------------------
# Aggregation & presentation
# ---------------------------------------------------------------------------
# Rounding for displayed scores (0-100 scale)
DISPLAY_SCORE_DECIMALS = 1
DISPLAY_SCORE_SCALE = 100  # 0..1 internal → 0..100 displayed

# Minimum score to show "recommended for review" badge in UI
REVIEW_BADGE_THRESHOLD = 0.60

# ---------------------------------------------------------------------------
# Pipeline behavior
# ---------------------------------------------------------------------------
MAX_RESUMES_PER_BATCH = 200
PARSE_CACHE_ENABLED = True
LOG_LEVEL = "INFO"

# ---------------------------------------------------------------------------
# Safety rails
# ---------------------------------------------------------------------------
# The tool must NEVER auto-reject. This flag exists so we can grep for it
# and confirm the pipeline has no silent rejection logic. Leave it False.
ENABLE_AUTO_REJECT = False
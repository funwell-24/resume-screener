"""
Semantic similarity via sentence-transformers.

Optional upgrade over TF-IDF cosine. Catches paraphrased skills:
    "built ETL pipelines" ~ "data engineering experience"
    "ML models in production" ~ "machine learning deployment"

Requires:
    pip install sentence-transformers
    (first run downloads ~90 MB model to ~/.cache/huggingface/)

Enable by setting SIMILARITY_METHOD = "semantic" in config/settings.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class SemanticScore:
    score: float | None
    model_name: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "model_name": self.model_name,
            "note": self.note,
        }


@lru_cache(maxsize=1)
def _load_model() -> Any:
    """Load the sentence-transformer model. Cached for process lifetime."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(
            "Semantic scoring requires 'sentence-transformers'. "
            "Install with: pip install sentence-transformers"
        ) from exc
    return SentenceTransformer(settings.SEMANTIC_MODEL_NAME)


def is_available() -> bool:
    """Check whether sentence-transformers is importable without raising."""
    try:
        from sentence_transformers import SentenceTransformer  # noqa: F401
        return True
    except ImportError:
        return False


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def compute_semantic_scores(
    jd_text: str,
    resume_texts: dict[str, str],
) -> dict[str, SemanticScore]:
    """
    Compute semantic cosine similarity of each resume to the JD.

    Returns dict[str, SemanticScore]. If the model can't load or the JD
    is empty, `score` is None for every entry.
    """
    out: dict[str, SemanticScore] = {}

    if not jd_text or not jd_text.strip():
        return {k: SemanticScore(score=None) for k in resume_texts}

    valid = {k: v for k, v in resume_texts.items() if v and v.strip()}
    if not valid:
        return {k: SemanticScore(score=None) for k in resume_texts}

    try:
        model = _load_model()
    except ImportError as exc:
        logger.warning("Semantic scoring unavailable: %s", exc)
        return {
            k: SemanticScore(score=None, note="sentence-transformers not installed")
            for k in resume_texts
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Model load failed: %s", exc)
        return {
            k: SemanticScore(score=None, note="model load failed")
            for k in resume_texts
        }

    try:
        jd_vec = model.encode(jd_text, normalize_embeddings=True)
        keys = list(valid.keys())
        resume_vecs = model.encode(
            [valid[k] for k in keys],
            normalize_embeddings=True,
            batch_size=8,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Encoding failed: %s", exc)
        return {
            k: SemanticScore(score=None, note="encoding failed")
            for k in resume_texts
        }

    for i, key in enumerate(keys):
        score = _cosine(jd_vec, resume_vecs[i])
        # Cosine in [-1, 1] → clip negatives to 0
        score = max(0.0, min(1.0, score))
        out[key] = SemanticScore(
            score=score,
            model_name=settings.SEMANTIC_MODEL_NAME,
        )

    # Fill missing keys
    for key in resume_texts:
        out.setdefault(
            key,
            SemanticScore(score=None, note="not processed"),
        )

    return out
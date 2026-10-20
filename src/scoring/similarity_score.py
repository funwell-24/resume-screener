"""
TF-IDF cosine similarity between resume and JD.

Fit TF-IDF on [JD + all resumes] together so IDF weights reflect
THIS candidate pool (matching how recruiters actually read — the
same word appearing in every resume becomes less informative).

Handles:
    - Single resume (degenerate — all scores become 0)
    - Empty text (returns None)
    - Shared function to also return the top-K shared terms (for
      explainability in the UI)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class SimilarityScore:
    score: float | None
    top_shared_terms: list[tuple[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "top_shared_terms": self.top_shared_terms,
        }


def _build_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        stop_words="english",
        lowercase=True,
        ngram_range=settings.TFIDF_NGRAM_RANGE,
        min_df=settings.TFIDF_MIN_DF,
        max_features=settings.TFIDF_MAX_FEATURES,
        sublinear_tf=True,
    )


def compute_similarity_scores(
    jd_text: str,
    resume_texts: dict[str, str],
    top_k_terms: int = 10,
) -> dict[str, SimilarityScore]:
    """
    Compute TF-IDF cosine similarity of each resume to the JD.

    Parameters
    ----------
    jd_text : str
        Cleaned job description text.
    resume_texts : dict[str, str]
        {candidate_id_or_filename: cleaned_resume_text}
    top_k_terms : int
        How many top shared terms to return per resume (for UI).

    Returns
    -------
    dict[str, SimilarityScore]
        One entry per resume key. `score` is None if inputs are unusable.
    """
    out: dict[str, SimilarityScore] = {}

    # Guard: need a JD and at least one non-empty resume
    if not jd_text or not jd_text.strip():
        for key in resume_texts:
            out[key] = SimilarityScore(score=None)
        return out

    valid = {k: v for k, v in resume_texts.items() if v and v.strip()}
    if not valid:
        for key in resume_texts:
            out[key] = SimilarityScore(score=None)
        return out

    # Single resume → cosine always 1.0 or 0.0 depending on whether JD shares any
    # term. That's misleading; return None so aggregator redistributes weight.
    if len(valid) == 1:
        only_key = next(iter(valid))
        out[only_key] = SimilarityScore(score=None)
        for key in resume_texts:
            out.setdefault(key, SimilarityScore(score=None))
        return out

    keys = list(valid.keys())
    docs = [jd_text] + [valid[k] for k in keys]

    try:
        vectorizer = _build_vectorizer()
        matrix = vectorizer.fit_transform(docs)
    except ValueError as exc:
        # Happens if after stopword removal everything is empty
        logger.warning("TF-IDF fit failed: %s", exc)
        for key in resume_texts:
            out[key] = SimilarityScore(score=None)
        return out

    jd_vec = matrix[0:1]
    resume_vecs = matrix[1:]

    sims = cosine_similarity(jd_vec, resume_vecs).flatten()

    # Top shared terms per resume for explainability
    feature_names = np.array(vectorizer.get_feature_names_out())
    jd_row = jd_vec.toarray().flatten()

    for i, key in enumerate(keys):
        resume_row = resume_vecs[i].toarray().flatten()
        # Weight = product of tf-idf scores → top shared terms
        shared = jd_row * resume_row
        nonzero_idx = np.where(shared > 0)[0]
        if len(nonzero_idx) > 0:
            top_idx = nonzero_idx[np.argsort(-shared[nonzero_idx])[:top_k_terms]]
            top_terms = [(feature_names[j], float(shared[j])) for j in top_idx]
        else:
            top_terms = []

        out[key] = SimilarityScore(
            score=float(max(0.0, min(1.0, sims[i]))),
            top_shared_terms=top_terms,
        )

    # Ensure every input key has an entry
    for key in resume_texts:
        out.setdefault(key, SimilarityScore(score=None))

    return out
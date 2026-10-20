"""
AI Resume Screening & Ranking Tool — internal package.

This __init__.py exists so `src` is a proper package (importable with
`from src.parsing import ...`). It intentionally imports NOTHING from
submodules — doing so would:
    - Slow startup (spaCy model loads)
    - Create circular-import risk with `config`
    - Break `python -m src.some.script` invocations

Every subpackage is opt-in:

    from src.parsing     import parse_pdf
    from src.extraction  import extract_skills
    from src.scoring     import score_batch
    from src.pipeline    import run_batch
    from src.models      import Candidate, JobDescription
    from src.evaluation  import compute_set_metrics
    from src.utils       import setup_logging
"""

__version__ = "1.0.0"
__author__ = "Resume Screener Project"

__all__ = ["__version__"]
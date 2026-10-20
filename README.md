<<<<<<< HEAD
# AI Resume Screener

**An explainable, human-in-the-loop resume screening and ranking tool.**

Given a job description and a batch of PDF resumes, the tool parses each
resume, extracts structured information (skills, education, experience,
contact), scores each candidate against the JD, and returns a ranked list —
with **every score backed by a visible rationale**.

> ⚠️ **This tool is decision-support only.** Scores are computed from
> keyword overlap and text similarity. They can miss relevant experience,
> misjudge transferable skills, and penalize non-standard resume formats.
> **Do not use these scores to automatically reject or rank candidates.**
> Every candidate should be reviewed by a human before any action is taken.

---

## What it does

| Step | What happens |
|------|--------------|
| **1. Input** | Recruiter provides a JD (pasted or uploaded) and uploads multiple PDF resumes. |
| **2. Parse** | PyMuPDF extracts text; Tesseract OCR kicks in for scanned PDFs. |
| **3. Extract** | spaCy + a curated skill taxonomy pulls out skills, degrees, years of experience, and contact info. |
| **4. Score** | Keyword overlap, TF-IDF or semantic similarity, and experience fit are combined into a transparent 0–100 score. |
| **5. Review** | Candidates are ranked; each row shows matched/missing skills and score components for recruiter review. |

---

## Quickstart

```bash
# 1. Clone and install
git clone <repo-url> resume-screener
cd resume-screener

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev]"            # editable install with dev tools
python -m spacy download en_core_web_sm

# 2. Seed data (sample JD + placeholder resume)
python scripts/ingest_sample_resumes.py --placeholder

# 3. Try the CLI
python scripts/run_cli.py \
    data/job_descriptions/sample_jd.txt \
    data/resumes/ \
    -v

# 4. Or launch the UI
streamlit run app.py
=======
# resume-screener
>>>>>>> origin/main

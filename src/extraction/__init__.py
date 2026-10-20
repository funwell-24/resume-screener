"""
Information extraction layer.

Given cleaned resume text, produce structured data:
    - skills        (set of canonical skill names)
    - education     (degree level, institution, field)
    - experience    (total years, per-job entries)
    - contact       (name, email, phone, links)
    - sections      (raw text partitioned by section)

Public API — import from this module, not from submodules.
"""

from .skills import (
    extract_skills,
    extract_skills_with_evidence,
    extract_required_skills_from_jd,
    skills_by_section,
    load_taxonomy,
)
from .education import extract_education, EducationInfo, EducationEntry
from .experience import (
    extract_experience,
    required_years_from_jd,
    ExperienceInfo,
    ExperienceEntry,
)
from .contact import extract_contact, ContactInfo
from .sections import split_sections, get_section, ResumeSections

__all__ = [
    # Skills
    "extract_skills",
    "extract_skills_with_evidence",
    "extract_required_skills_from_jd",
    "skills_by_section",
    "load_taxonomy",
    # Education
    "extract_education",
    "EducationInfo",
    "EducationEntry",
    # Experience
    "extract_experience",
    "required_years_from_jd",
    "ExperienceInfo",
    "ExperienceEntry",
    # Contact
    "extract_contact",
    "ContactInfo",
    # Sections
    "split_sections",
    "get_section",
    "ResumeSections",
]
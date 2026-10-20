"""
Package metadata for the resume screener.

Why have setup.py at all?
    1. `pip install -e .` makes `from src.parsing import ...` work from
       ANY directory — no more `sys.path.insert(...)` hacks in scripts.
    2. It declares the package name, version, and dependencies that
       PyPI / pip tools expect.
    3. `python -m src.pipeline.batch_runner` (module execution) works
       without needing to be in the project root.

Once installed:
    pip install -e .              # editable install (recommended for dev)
    pip install .                 # normal install (build → dist/ → install)
"""

from pathlib import Path

from setuptools import setup, find_packages


# Read long description from README for PyPI metadata
_here = Path(__file__).parent
_long_description = (
    (_here / "README.md").read_text(encoding="utf-8")
    if (_here / "README.md").exists() else ""
)


setup(
    name="resume-screener",
    version="1.0.0",
    description=(
        "AI resume screening and ranking tool — "
        "explainable, human-in-the-loop candidate shortlisting."
    ),
    long_description=_long_description,
    long_description_content_type="text/markdown",
    author="Resume Screener Project",
    license="MIT",

    # find_packages excludes tests and scripts by default.
    # `src` is the only package we install.
    packages=find_packages(
        include=["src", "src.*"],
        exclude=["tests", "tests.*", "scripts", "scripts.*"],
    ),

    python_requires=">=3.10",

    # Read deps from requirements.txt to keep a single source of truth.
    # Optional groups (OCR, semantic) stay in requirements.txt but
    # aren't hard requirements — they're documented as extras below.
    install_requires=[
        "PyMuPDF>=1.24,<2.0",
        "spacy>=3.7,<4.0",
        "scikit-learn>=1.4,<2.0",
        "numpy>=1.26,<3.0",
        "pandas>=2.1,<3.0",
        "scipy>=1.11,<2.0",
        "streamlit>=1.33,<2.0",
        "matplotlib>=3.8,<4.0",
    ],

    extras_require={
        # pip install -e ".[ocr]"
        "ocr": [
            "pytesseract>=0.3.10",
            "Pillow>=10.0,<12.0",
        ],
        # pip install -e ".[semantic]"
        "semantic": [
            "sentence-transformers>=2.7,<4.0",
        ],
        # pip install -e ".[dev]"
        "dev": [
            "pytest>=8.0,<9.0",
            "pytest-cov>=5.0,<7.0",
            "black>=24.0,<26.0",
            "ruff>=0.5,<1.0",
        ],
        # pip install -e ".[all]"
        "all": [
            "pytesseract>=0.3.10",
            "Pillow>=10.0,<12.0",
            "sentence-transformers>=2.7,<4.0",
            "pytest>=8.0,<9.0",
            "pytest-cov>=5.0,<7.0",
            "black>=24.0,<26.0",
            "ruff>=0.5,<1.0",
        ],
    },

    entry_points={
        "console_scripts": [
            # `resume-screener <jd.txt> <resumes/>` → runs run_cli.py
            "resume-screener=scripts.run_cli:main",
        ],
    },

    # Don't ship local data or the config taxonomy as package data —
    # they're user-editable and belong outside site-packages.
    include_package_data=False,
    zip_safe=False,

    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Human Resources",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Text Processing :: Linguistic",
    ],
)
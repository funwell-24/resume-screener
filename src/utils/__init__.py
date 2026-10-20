"""
Shared utilities.

Public API:
    setup_logging() / get_logger(name)
        Consistent logging across the whole app.

    read_json / write_json / read_text / write_text
        Safe file I/O with atomic writes and sane defaults.

    validate_pdf / validate_file_size / validate_batch_input
        Fail-fast input checks with useful error messages.
"""

from .logger import setup_logging, get_logger
from .file_io import (
    read_json,
    write_json,
    read_text,
    write_text,
    ensure_dir,
    safe_filename,
)
from .validators import (
    ValidationError,
    validate_pdf,
    validate_file_size,
    validate_batch_input,
    validate_jd_text,
)

__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    # I/O
    "read_json",
    "write_json",
    "read_text",
    "write_text",
    "ensure_dir",
    "safe_filename",
    # Validators
    "ValidationError",
    "validate_pdf",
    "validate_file_size",
    "validate_batch_input",
    "validate_jd_text",
]
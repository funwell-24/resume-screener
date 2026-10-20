"""
Safe file I/O helpers.

Design:
    - Atomic writes: write to a temp file, then os.replace() â€” so a
      crash mid-write never leaves a half-written JSON on disk.
    - UTF-8 by default everywhere.
    - JSON helpers handle dataclasses and sets out of the box.
    - Read helpers return defaults on missing file instead of raising
      (unless you pass raise_on_missing=True).
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

def ensure_dir(path: str | Path) -> Path:
    """Create directory (and parents) if missing. Returns the Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_filename(name: str, max_length: int = 200) -> str:
    """
    Sanitize a string for use as a filename.

    Removes path separators, control chars, and Windows-reserved names.
    Keeps alphanumerics, dots, hyphens, underscores.
    """
    cleaned = re.sub(r"[^\w.\-]", "_", name).strip("._")

    if not cleaned:
        cleaned = "file"

    # Windows reserved names
    reserved = {
        "con", "prn", "aux", "nul",
        *{f"com{i}" for i in range(1, 10)},
        *{f"lpt{i}" for i in range(1, 10)},
    }
    stem = cleaned.split(".")[0].lower()
    if stem in reserved:
        cleaned = f"_{cleaned}"

    if len(cleaned) > max_length:
        # Preserve extension if present
        if "." in cleaned:
            base, ext = cleaned.rsplit(".", 1)
            cleaned = base[: max_length - len(ext) - 1] + "." + ext
        else:
            cleaned = cleaned[:max_length]

    return cleaned


# ---------------------------------------------------------------------------
# Text I/O
# ---------------------------------------------------------------------------

def read_text(
    path: str | Path,
    default: str | None = None,
    *,
    raise_on_missing: bool = False,
) -> str | None:
    """Read UTF-8 text. Returns `default` if missing (unless raise_on_missing)."""
    p = Path(path)
    if not p.exists():
        if raise_on_missing:
            raise FileNotFoundError(f"File not found: {p}")
        return default
    try:
        return p.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Failed to read %s: %s", p, exc)
        if raise_on_missing:
            raise
        return default


def write_text(
    path: str | Path,
    content: str,
    *,
    atomic: bool = True,
) -> None:
    """Write UTF-8 text. Atomic by default."""
    p = Path(path)
    ensure_dir(p.parent)

    if atomic:
        _atomic_write(p, content.encode("utf-8"))
    else:
        p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------

def _json_default(obj: Any) -> Any:
    """Fallback serializer: dataclass â†’ dict, set â†’ sorted list."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, set):
        return sorted(obj)
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def read_json(
    path: str | Path,
    default: Any = None,
    *,
    raise_on_missing: bool = False,
) -> Any:
    """Read JSON. Returns `default` if missing. Raises on malformed JSON."""
    p = Path(path)
    if not p.exists():
        if raise_on_missing:
            raise FileNotFoundError(f"File not found: {p}")
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        logger.error("Malformed JSON in %s: %s", p, exc)
        raise
    except OSError as exc:
        logger.warning("Failed to read %s: %s", p, exc)
        if raise_on_missing:
            raise
        return default


def write_json(
    path: str | Path,
    obj: Any,
    *,
    indent: int = 2,
    atomic: bool = True,
) -> None:
    """
    Write JSON. Handles dataclasses, sets, and Path objects automatically.

    Atomic by default â€” safe against crashes mid-write.
    """
    p = Path(path)
    ensure_dir(p.parent)

    serialized = json.dumps(
        obj,
        indent=indent,
        ensure_ascii=False,
        default=_json_default,
    )
    payload = serialized.encode("utf-8")

    if atomic:
        _atomic_write(p, payload)
    else:
        p.write_bytes(payload)


# ---------------------------------------------------------------------------
# Atomic write helper
# ---------------------------------------------------------------------------

def _atomic_write(path: Path, data: bytes) -> None:
    """
    Write bytes to a temp file in the SAME directory, then rename.

    Same directory is required for os.replace to be atomic across
    filesystems. Preserves existing file permissions when possible.
    """
    directory = path.parent
    fd, tmp_path = tempfile.mkstemp(
        dir=str(directory),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            tmp_file.write(data)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        # Preserve permissions of the original if it exists
        if path.exists():
            try:
                os.chmod(tmp_path, path.stat().st_mode)
            except OSError:
                pass

        os.replace(tmp_path, path)
    except Exception:
        # Clean up the temp file if anything went wrong
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
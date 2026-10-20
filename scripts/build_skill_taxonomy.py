"""
Build / extend config/skills.json from one or more source files.

Sources can be:
    - A JSON file in our native taxonomy format
    - A plain .txt file with one skill per line (auto-categorized)
    - A Python module defining `SKILLS` list (advanced)

Modes:
    --merge           Merge sources into existing skills.json
    --replace         Overwrite skills.json with sources only
    --add             Add a single skill (with optional aliases)
    --list            Print current taxonomy (debug)
    --validate        Check skills.json for duplicates or bad entries

Examples
--------
    # Add a new skill with aliases
    python scripts/build_skill_taxonomy.py --add "graphql" --aliases "graph ql"

    # Merge in a plain-text list (auto-categorized as 'other')
    python scripts/build_skill_taxonomy.py --merge data/labeled/extra_skills.txt

    # Validate the current taxonomy
    python scripts/build_skill_taxonomy.py --validate

    # Print summary
    python scripts/build_skill_taxonomy.py --list
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make src importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import settings
from src.utils import setup_logging, get_logger, write_json, read_json

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Taxonomy manipulation helpers
# ---------------------------------------------------------------------------

def load_taxonomy() -> dict[str, dict[str, list[str]]]:
    """Load skills.json (or return empty structure if missing)."""
    if not settings.SKILLS_TAXONOMY_PATH.exists():
        return {}
    return read_json(settings.SKILLS_TAXONOMY_PATH, default={}) or {}


def save_taxonomy(taxonomy: dict[str, dict[str, list[str]]]) -> None:
    """Write taxonomy back to config/skills.json."""
    write_json(settings.SKILLS_TAXONOMY_PATH, taxonomy)
    logger.info("Wrote taxonomy: %s", settings.SKILLS_TAXONOMY_PATH)


def find_existing_category(
    taxonomy: dict[str, dict[str, list[str]]],
    skill: str,
) -> tuple[str, str] | None:
    """Return (category, canonical_skill) if the skill exists anywhere."""
    skill = skill.lower().strip()
    for category, skills in taxonomy.items():
        for canonical, aliases in skills.items():
            if canonical.lower() == skill:
                return category, canonical
            if skill in (a.lower() for a in aliases):
                return category, canonical
    return None


def add_skill(
    taxonomy: dict[str, dict[str, list[str]]],
    skill: str,
    aliases: list[str] | None = None,
    category: str = "other",
) -> bool:
    """
    Add a skill to a category. Returns True if actually added,
    False if it already existed (in the same category).
    """
    aliases = aliases or []
    skill = skill.strip()
    if not skill:
        return False

    existing = find_existing_category(taxonomy, skill)
    if existing:
        cat, canonical = existing
        logger.info("Skill already present: %r → %r (category: %s)",
                    skill, canonical, cat)
        return False

    taxonomy.setdefault(category, {})
    taxonomy[category][skill.lower()] = [a.lower() for a in aliases if a.strip()]
    return True


def merge_source(
    taxonomy: dict[str, dict[str, list[str]]],
    source_path: Path,
) -> int:
    """
    Merge a source file into the taxonomy. Returns count of skills added.

    Source formats:
        .json  → native taxonomy format (validated)
        .txt   → one skill per line
        otherwise → error
    """
    if not source_path.exists():
        logger.error("Source not found: %s", source_path)
        return 0

    added = 0

    if source_path.suffix.lower() == ".json":
        try:
            incoming = read_json(source_path, raise_on_missing=True)
        except Exception as exc:  # noqa: BLE001
            logger.error("Could not parse %s: %s", source_path, exc)
            return 0

        if not isinstance(incoming, dict):
            logger.error("JSON source must be an object at top level")
            return 0

        for category, skills in incoming.items():
            if not isinstance(skills, dict):
                logger.warning("Skipping non-dict category %r", category)
                continue
            for canonical, aliases in skills.items():
                if add_skill(taxonomy, canonical, aliases or [], category):
                    added += 1

    elif source_path.suffix.lower() == ".txt":
        for line in source_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Support "skill: alias1, alias2" syntax
            if ":" in line:
                canonical, alias_str = line.split(":", 1)
                aliases = [a.strip() for a in alias_str.split(",") if a.strip()]
                canonical = canonical.strip()
            else:
                canonical, aliases = line, []
            if add_skill(taxonomy, canonical, aliases, category="other"):
                added += 1

    else:
        logger.error("Unsupported source type: %s", source_path.suffix)
        return 0

    logger.info("Merged %s: %d skills added", source_path.name, added)
    return added


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_taxonomy(taxonomy: dict) -> list[str]:
    """Return a list of validation issues (empty = OK)."""
    issues: list[str] = []
    seen_canonical: dict[str, str] = {}  # canonical → category

    for category, skills in taxonomy.items():
        if not isinstance(skills, dict):
            issues.append(f"Category {category!r} is not a dict")
            continue
        for canonical, aliases in skills.items():
            key = canonical.strip().lower()
            if not key:
                issues.append(f"Empty canonical skill in category {category!r}")
                continue
            if key in seen_canonical:
                issues.append(
                    f"Duplicate canonical skill {canonical!r}: "
                    f"in {seen_canonical[key]!r} and {category!r}"
                )
            else:
                seen_canonical[key] = category

            if not isinstance(aliases, list):
                issues.append(f"Aliases for {canonical!r} must be a list")
                continue
            for alias in aliases:
                if not isinstance(alias, str) or not alias.strip():
                    issues.append(f"Empty alias in {category}/{canonical}")

    return issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build or extend config/skills.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "sources", nargs="*", type=Path,
        help="Source files to merge (.json or .txt)",
    )
    parser.add_argument(
        "--merge", action="store_true",
        help="Merge sources into existing skills.json (default: replace)",
    )
    parser.add_argument(
        "--add", metavar="SKILL",
        help="Add a single skill",
    )
    parser.add_argument(
        "--aliases", metavar="A,B",
        help="Comma-separated aliases for --add",
        default="",
    )
    parser.add_argument(
        "--category", default="other",
        help="Category for --add (default: other)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List current taxonomy and exit",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Validate current taxonomy and exit",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would change without writing",
    )

    args = parser.parse_args()

    setup_logging()

    # ---- Load ---------------------------------------------------------
    taxonomy = load_taxonomy() if args.merge else {}

    # ---- Read-only modes ---------------------------------------------
    if args.list:
        current = load_taxonomy()
        print(f"\nCurrent taxonomy: {settings.SKILLS_TAXONOMY_PATH}\n")
        total = 0
        for category, skills in current.items():
            print(f"  [{category}] ({len(skills)} skills)")
            for canonical, aliases in sorted(skills.items()):
                alias_str = f"  (aliases: {', '.join(aliases)})" if aliases else ""
                print(f"    • {canonical}{alias_str}")
                total += 1
        print(f"\nTotal: {total} skills across {len(current)} categories\n")
        return 0

    if args.validate:
        current = load_taxonomy()
        issues = validate_taxonomy(current)
        if not issues:
            print(f"✓ Taxonomy is valid ({settings.SKILLS_TAXONOMY_PATH})")
            return 0
        print(f"✗ Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    # ---- Mutating modes ----------------------------------------------
    changed = 0

    if args.add:
        aliases = [a.strip() for a in args.aliases.split(",") if a.strip()]
        if add_skill(taxonomy, args.add, aliases, args.category):
            changed += 1
            print(f"✓ Added {args.add!r} to {args.category!r}")
        else:
            print(f"ℹ {args.add!r} already present — no change")

    for source in args.sources:
        changed += merge_source(taxonomy, source)

    if changed == 0 and not args.add:
        print("Nothing to do. Use --help for usage.")
        return 0

    if args.dry_run:
        print(f"\nDry run — would write {changed} new skill(s). No changes made.")
        return 0

    # ---- Validate before write --------------------------------------
    issues = validate_taxonomy(taxonomy)
    if issues:
        print(f"✗ Refusing to write — {len(issues)} validation issue(s):")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    save_taxonomy(taxonomy)
    print(f"\n✓ Wrote {changed} new skill(s) to {settings.SKILLS_TAXONOMY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
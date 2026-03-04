#!/usr/bin/env python3
"""
Add new verse placeholders to existing collections.

This command adds verse entries to the canonical YAML file. Markdown files
will be auto-created by verse-generate if they don't exist.

Usage:
    # Add single verse (YAML only, default)
    verse-add --collection hanuman-chalisa --verse 44

    # Add multiple verses (range)
    verse-add --collection hanuman-chalisa --verse 44-50

    # Add with markdown files (optional, usually not needed)
    verse-add --collection hanuman-chalisa --verse 44 --markdown
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import yaml


def parse_verse_range(verse_arg: str) -> List[int]:
    """
    Parse verse argument into list of verse numbers.

    Args:
        verse_arg: Verse number or range (e.g., "5" or "5-10")

    Returns:
        List of verse numbers
    """
    if '-' in verse_arg:
        start, end = verse_arg.split('-')
        return list(range(int(start), int(end) + 1))
    else:
        return [int(verse_arg)]


def detect_chapter_format(verse_keys: List[str]) -> Optional[Tuple[int, str]]:
    """
    Detect if verse IDs use chapter-based format (e.g., chapter-01-shloka-01).

    Args:
        verse_keys: List of verse IDs

    Returns:
        Tuple of (detected_chapter_number, chapter_format_string) if chapter-based,
        None if simple format
        e.g., (1, "{:02d}") for chapter-01-shloka-01
    """
    if not verse_keys:
        return None

    first_key = verse_keys[0]

    # Try to detect chapter-XX pattern
    match = re.search(r'chapter-(\d+)', first_key)
    if match:
        chapter_num = int(match.group(1))
        chapter_str = match.group(1)

        # Determine padding
        if len(chapter_str) > 1 and chapter_str[0] == '0':
            padding = len(chapter_str)
            chapter_format = f"{{:0{padding}d}}"
        else:
            chapter_format = "{:d}"

        return chapter_num, chapter_format

    return None


def infer_default_format_from_collection(collection_info: dict) -> Tuple[str, str]:
    """
    Infer default verse format from collection metadata.

    Args:
        collection_info: Collection configuration from collections.yml

    Returns:
        Tuple of (prefix, format_string) based on collection metadata
    """
    # Check if collection has chapters (multi-chapter format)
    has_chapters = collection_info.get('chapters', 0) > 0

    # Check for explicit verse_format hint
    verse_format = collection_info.get('verse_format', 'shloka' if has_chapters else 'verse')

    if has_chapters:
        # Multi-chapter format: chapter-01-shloka-01
        return f"chapter-01-{verse_format}", "{:02d}"
    else:
        # Simple format: verse-01 or chaupai-01
        return verse_format, "{:02d}"


def infer_verse_format(existing_verses: dict, collection_info: Optional[dict] = None) -> Tuple[str, str]:
    """
    Infer verse ID format from existing verses or collection metadata.

    Args:
        existing_verses: Dictionary of existing verse entries
        collection_info: Optional collection configuration from collections.yml

    Returns:
        Tuple of (prefix, format_string)
        e.g., ("verse", "{:02d}") for verse-01, verse-02, etc.
        e.g., ("chaupai", "{:d}") for chaupai-1, chaupai-2, etc.
        e.g., ("chapter-01-shloka", "{:02d}") for chapter-01-shloka-01
    """
    # Get a sample verse key
    sample_keys = list(existing_verses.keys()) if existing_verses else []

    # Filter out metadata keys (keys starting with _)
    verse_keys = [k for k in sample_keys if not k.startswith('_')]

    if verse_keys:
        # Analyze first verse key to infer pattern
        first_key = verse_keys[0]

        # Try to parse pattern: prefix-number
        match = re.match(r'^([a-z\-]+)-(\d+)$', first_key)
        if match:
            prefix = match.group(1)
            number = match.group(2)

            # Determine if zero-padded
            if len(number) > 1 and number[0] == '0':
                # Zero-padded (e.g., 01, 02)
                padding = len(number)
                format_str = f"{{:0{padding}d}}"
            else:
                # No padding (e.g., 1, 2)
                format_str = "{:d}"

            return prefix, format_str

    # No existing verses - try to infer from collection metadata
    if collection_info:
        return infer_default_format_from_collection(collection_info)

    # Fallback to default
    return "verse", "{:02d}"


def get_collection_info(project_dir: Path, collection_key: str) -> dict:
    """
    Get collection information from collections.yml.

    Args:
        project_dir: Project root directory
        collection_key: Collection key

    Returns:
        Collection configuration dict
    """
    collections_file = project_dir / "_data" / "collections.yml"
    if not collections_file.exists():
        print(f"Error: {collections_file} not found")
        sys.exit(1)

    with open(collections_file, 'r') as f:
        collections = yaml.safe_load(f) or {}

    if collection_key not in collections:
        print(f"Error: Collection '{collection_key}' not found in collections.yml")
        print(f"Available collections: {', '.join(collections.keys())}")
        sys.exit(1)

    return collections[collection_key]


def count_non_meta_verses(data: dict) -> int:
    """Count non-metadata verse entries in canonical YAML data."""
    return len([k for k in data.keys() if not k.startswith('_')])


def sync_collection_total_verses(project_dir: Path, collection_key: str, total_verses: int) -> Tuple[bool, Optional[int], int]:
    """
    Sync total_verses for a collection in _data/collections.yml.

    Preserves existing comments/formatting by editing only the target collection block.

    Returns:
        Tuple of (changed, previous_value, new_value)
    """
    collections_file = project_dir / "_data" / "collections.yml"
    if not collections_file.exists():
        return False, None, total_verses

    text = collections_file.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    start_idx = None
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(collection_key)}:\s*$", line.rstrip("\n")):
            start_idx = i
            break

    if start_idx is None:
        return False, None, total_verses

    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped and not lines[i].startswith((" ", "\t", "#")):
            end_idx = i
            break

    block_lines = lines[start_idx + 1:end_idx]
    total_idx = None
    old_value: Optional[int] = None
    prop_indent = "  "

    for j, line in enumerate(block_lines):
        prop_match = re.match(r"^(\s+)\S", line)
        if prop_match:
            prop_indent = prop_match.group(1)
            break

    for j, line in enumerate(block_lines):
        m = re.match(r"^(\s*)total_verses:\s*([0-9]+)\s*$", line.rstrip("\n"))
        if m:
            total_idx = j
            old_value = int(m.group(2))
            indent = m.group(1)
            block_lines[j] = f"{indent}total_verses: {total_verses}\n"
            break

    if total_idx is None:
        insert_at = len(block_lines)
        for j in range(len(block_lines) - 1, -1, -1):
            if block_lines[j].strip():
                insert_at = j + 1
                break
        block_lines.insert(insert_at, f"{prop_indent}total_verses: {total_verses}\n")

    new_lines = lines[:start_idx + 1] + block_lines + lines[end_idx:]
    new_text = "".join(new_lines)
    changed = new_text != text
    if changed:
        collections_file.write_text(new_text, encoding="utf-8")
    return changed, old_value, total_verses


def add_verses_to_yaml(project_dir: Path, collection_key: str, verse_numbers: List[int], custom_format: Optional[str] = None, chapter: Optional[int] = None, collection_info: Optional[dict] = None) -> Tuple[int, int, str, int]:
    """
    Add verse placeholders to canonical YAML file.

    Args:
        project_dir: Project root directory
        collection_key: Collection key
        verse_numbers: List of verse numbers to add
        custom_format: Optional custom format (overrides inferred format)
        chapter: Optional chapter number for chapter-based formats
        collection_info: Optional collection configuration from collections.yml

    Returns:
        Tuple of (added_count, skipped_count, format_used, canonical_total_verses)
    """
    yaml_files = [
        project_dir / "data" / "verses" / f"{collection_key}.yaml",
        project_dir / "data" / "verses" / f"{collection_key}.yml",
    ]

    # Find existing YAML file or create new one
    yaml_file = None
    existing_verses = {}

    for yf in yaml_files:
        if yf.exists():
            yaml_file = yf
            with open(yf, 'r') as f:
                existing_verses = yaml.safe_load(f) or {}
            break

    if yaml_file is None:
        yaml_file = project_dir / "data" / "verses" / f"{collection_key}.yaml"
        yaml_file.parent.mkdir(parents=True, exist_ok=True)

    # Infer format from existing verses or collection metadata (unless custom format provided)
    if custom_format:
        # Parse custom format: "prefix-{format}"
        match = re.match(r'^([a-z\-]+)-(.+)$', custom_format)
        if match:
            prefix = match.group(1)
            format_str = match.group(2)
        else:
            print(f"Warning: Invalid custom format '{custom_format}', using inferred format")
            prefix, format_str = infer_verse_format(existing_verses, collection_info)
    else:
        prefix, format_str = infer_verse_format(existing_verses, collection_info)

        # If format was inferred from collection metadata, inform the user
        verse_keys = [k for k in existing_verses.keys() if not k.startswith('_')] if existing_verses else []
        if not verse_keys and collection_info:
            print("  ℹ️  No existing verses found. Using format from collection metadata.")
            if collection_info.get('chapters', 0) > 0:
                print(f"     Collection has {collection_info.get('chapters')} chapters - using chapter-based format")

    # Handle chapter-based formats
    verse_keys = [k for k in existing_verses.keys() if not k.startswith('_')]
    chapter_info = detect_chapter_format(verse_keys)

    if chapter and chapter_info:
        # Replace chapter number in prefix
        detected_chapter, chapter_format = chapter_info
        old_chapter_str = chapter_format.format(detected_chapter)
        new_chapter_str = chapter_format.format(chapter)

        # Replace chapter number in prefix
        prefix = prefix.replace(f"chapter-{old_chapter_str}", f"chapter-{new_chapter_str}")

        print(f"  📖 Using chapter {chapter} (detected format: chapter-{chapter_format})")
    elif chapter and not chapter_info:
        print("  ⚠️  Warning: --chapter flag provided but collection doesn't use chapter-based format")
        print("     Ignoring --chapter flag")

    format_used = f"{prefix}-{format_str}"

    added = 0
    skipped = 0
    new_verses = []

    # Check which verses need to be added
    for verse_num in verse_numbers:
        verse_id = f"{prefix}-{format_str.format(verse_num)}"

        if verse_id in existing_verses:
            print(f"  ⚠️  Skipped {verse_id} (already exists)")
            skipped += 1
        else:
            new_verses.append(verse_id)
            print(f"  ✓ Will add {verse_id} to {yaml_file.name}")
            added += 1

    # Append new verses to the end of the file (preserves comments and formatting)
    if new_verses:
        with open(yaml_file, 'a', encoding='utf-8') as f:
            # Add blank line before new verses
            f.write("\n")

            for i, verse_id in enumerate(new_verses):
                # Write verse entry
                f.write(f"{verse_id}:\n")
                f.write("  devanagari: ''\n")

                # Add blank line between verses (except after last)
                if i < len(new_verses) - 1:
                    f.write("\n")

    canonical_total_verses = count_non_meta_verses(existing_verses) + added
    return added, skipped, format_used, canonical_total_verses


def create_markdown_files(project_dir: Path, collection_key: str, verse_numbers: List[int], verse_prefix: str, format_str: str, chapter: Optional[int] = None) -> Tuple[int, int]:
    """
    Create markdown files for verses.

    Args:
        project_dir: Project root directory
        collection_key: Collection key
        verse_numbers: List of verse numbers to create
        verse_prefix: Verse prefix (e.g., "verse", "chaupai")
        format_str: Format string (e.g., "{:02d}", "{:d}")

    Returns:
        Tuple of (created_count, skipped_count)
    """
    verses_dir = project_dir / "_verses" / collection_key
    verses_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    skipped = 0

    for verse_num in verse_numbers:
        verse_id = f"{verse_prefix}-{format_str.format(verse_num)}"
        verse_file = verses_dir / f"{verse_id}.md"

        if verse_file.exists():
            print(f"  ⚠️  Skipped {verse_file.name} (already exists)")
            skipped += 1
        else:
            content = f"""---
layout: verse
collection: {collection_key}
verse_number: {verse_num}
title: "{verse_prefix.title()} {verse_num}"
---

Add verse content here.
"""
            verse_file.write_text(content)
            print(f"  ✓ Created {verse_file.name}")
            created += 1

    return created, skipped


def main():
    """Main entry point for verse-add command."""
    parser = argparse.ArgumentParser(
        description="Add new verse placeholders to existing collections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add single verse (YAML only, default)
  verse-add --collection hanuman-chalisa --verse 44

  # Add multiple verses (range)
  verse-add --collection hanuman-chalisa --verse 44-50

  # Add verses WITH markdown files (optional)
  verse-add --collection hanuman-chalisa --verse 44-50 --markdown

  # Add verses to specific chapter (for chapter-based formats)
  verse-add --collection bhagavad-gita --verse 1-10 --chapter 2

  # Add verses with custom verse ID format
  verse-add --collection bhagavad-gita --verse 1 --format "chapter-01-verse-{:02d}"

Note: verse-generate will auto-create markdown files if they don't exist

For more information:
  https://github.com/sanatan-learnings/sanatan-verse-sdk/blob/main/docs/usage.md
        """
    )

    parser.add_argument(
        "--collection",
        required=True,
        help="Collection key (e.g., hanuman-chalisa)"
    )

    parser.add_argument(
        "--verse",
        required=True,
        help="Verse number or range (e.g., 44 or 44-50)"
    )

    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Create markdown files (verse-generate will auto-create them if needed)"
    )

    parser.add_argument(
        "--format",
        default="verse-{:02d}",
        help="Verse ID format (default: verse-{:02d})"
    )

    parser.add_argument(
        "--chapter",
        type=int,
        help="Chapter number for chapter-based formats (e.g., --chapter 2 for chapter-02-shloka-01)"
    )

    args = parser.parse_args()

    try:
        project_dir = Path.cwd()

        # Parse verse numbers
        try:
            verse_numbers = parse_verse_range(args.verse)
        except ValueError:
            print(f"Error: Invalid verse format '{args.verse}'. Use a number (e.g., 44) or range (e.g., 44-50)")
            sys.exit(1)

        # Get collection info
        collection_info = get_collection_info(project_dir, args.collection)
        collection_name = collection_info.get('name', {}).get('en', args.collection)

        print()
        print(f"📝 Adding verses to {collection_name}")
        print(f"   Collection: {args.collection}")
        print(f"   Verses: {args.verse} ({len(verse_numbers)} verse(s))")
        if args.chapter:
            print(f"   Chapter: {args.chapter}")
        print()

        # Add to YAML
        print("Updating canonical YAML file:")
        custom_format = args.format if args.format != "verse-{:02d}" else None
        yaml_added, yaml_skipped, format_used, canonical_total_verses = add_verses_to_yaml(
            project_dir,
            args.collection,
            verse_numbers,
            custom_format,
            chapter=args.chapter,
            collection_info=collection_info
        )

        # Keep collections metadata synchronized with canonical verse count.
        total_changed, total_old, total_new = sync_collection_total_verses(
            project_dir,
            args.collection,
            canonical_total_verses
        )

        # Parse format for markdown creation
        match = re.match(r'^([a-z\-]+)-(.+)$', format_used)
        if match:
            verse_prefix = match.group(1)
            format_str = match.group(2)
        else:
            verse_prefix = "verse"
            format_str = "{:02d}"

        if yaml_added > 0:
            print(f"   Format: {format_used}")

        # Create markdown files (optional)
        if args.markdown:
            print()
            print("Creating markdown files:")
            md_created, md_skipped = create_markdown_files(
                project_dir,
                args.collection,
                verse_numbers,
                verse_prefix,
                format_str,
                chapter=args.chapter
            )
        else:
            md_created = 0
            md_skipped = len(verse_numbers)
            print()
            print("Skipping markdown files (verse-generate will create them automatically)")

        # Summary
        print()
        print("=" * 70)
        print("✅ Summary:")
        print(f"   YAML entries added: {yaml_added}")
        if yaml_skipped > 0:
            print(f"   YAML entries skipped: {yaml_skipped} (already exist)")
        if total_changed:
            if total_old is None:
                print(f"   collections.yml total_verses set: {total_new}")
            else:
                print(f"   collections.yml total_verses updated: {total_old} → {total_new}")
        else:
            print(f"   collections.yml total_verses already in sync: {total_new}")
        if args.markdown:
            print(f"   Markdown files created: {md_created}")
            if md_skipped > 0:
                print(f"   Markdown files skipped: {md_skipped} (already exist)")
        print()

        # Next steps
        if yaml_added > 0 or md_created > 0:
            print("📌 Next steps:")
            if yaml_added > 0:
                print(f"   1. Edit data/verses/{args.collection}.yaml to add Devanagari text")
            if md_created > 0:
                print(f"   2. Edit verse markdown files in _verses/{args.collection}/")
            print(f"   {3 if md_created > 0 else 2}. Generate content: verse-generate --collection {args.collection} --verse {verse_numbers[0]}")
            if not args.markdown:
                print("   Note: verse-generate will auto-create markdown files from YAML")
            print()

        sys.exit(0)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

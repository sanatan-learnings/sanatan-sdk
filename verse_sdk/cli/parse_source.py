#!/usr/bin/env python3
"""
Parse canonical source text into data/verses/<collection>.yaml.

Supports basic plain-text parsing with optional chapter detection.
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

CHAPTER_PATTERNS = [
    re.compile(r"^\s*Chapter\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"^\s*अध्याय\s+(\d+)\b"),
    re.compile(r"^\s*अध्यायः\s+(\d+)\b"),
]

FRONTMATTER_PATTERNS = [
    re.compile(r"\b(publisher|publication|press|edition|copyright|isbn)\b", re.IGNORECASE),
    re.compile(r"\b(all rights reserved|printed in|published by)\b", re.IGNORECASE),
    re.compile(r"\b(preface|foreword|introduction|table of contents|contents)\b", re.IGNORECASE),
]

VALID_CHAR_PATTERN = re.compile(r"[\u0900-\u097F\u0966-\u096F\w\s\.,;:'\"()\[\]\-—–!?/]+")


def _normalize_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _collect_files(source: Optional[List[str]], source_dir: Optional[str], source_glob: str) -> List[Path]:
    if source and source_dir:
        raise ValueError("Use either --source or --source-dir (not both).")

    files: List[Path] = []

    if source:
        files = [Path(p) for p in source]
    elif source_dir:
        root = Path(source_dir)
        files = sorted(root.glob(source_glob))
    else:
        raise ValueError("Provide --source or --source-dir.")

    missing = [str(p) for p in files if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Source files not found: {', '.join(missing)}")

    return files


def _detect_chapter(line: str) -> Optional[int]:
    for pattern in CHAPTER_PATTERNS:
        match = pattern.match(line)
        if match:
            return int(match.group(1))
    return None


def _is_frontmatter_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return any(pattern.search(stripped) for pattern in FRONTMATTER_PATTERNS)


def _noise_score(line: str) -> float:
    if not line.strip():
        return 0.0
    total = len(line)
    valid = len("".join(VALID_CHAR_PATTERN.findall(line)))
    if total == 0:
        return 0.0
    return 1.0 - (valid / total)


def _is_verse_candidate(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    devanagari_chars = len(re.findall(r"[\u0900-\u097F]", stripped))
    if devanagari_chars >= 6:
        return True
    letters = len(re.findall(r"[A-Za-z]", stripped))
    return letters >= 12


def _filter_lines(
    lines: List[str],
    *,
    filter_frontmatter: bool,
    filter_ocr_noise: bool,
    frontmatter_max_lines: int,
    noise_threshold: float,
) -> Tuple[List[str], Dict[str, int]]:
    stats = {
        "lines_scanned": len(lines),
        "lines_frontmatter_dropped": 0,
        "lines_noise_dropped": 0,
    }

    filtered = lines[:]

    if filter_frontmatter:
        scan_limit = min(frontmatter_max_lines, len(filtered))
        first_content_idx = None
        for idx in range(scan_limit):
            line = filtered[idx]
            if _detect_chapter(line) is not None or _is_verse_candidate(line):
                first_content_idx = idx
                break

        if first_content_idx is not None and first_content_idx > 0:
            dropped = 0
            for line in filtered[:first_content_idx]:
                if line.strip():
                    dropped += 1
            stats["lines_frontmatter_dropped"] += dropped
            filtered = filtered[first_content_idx:]

        cleaned: List[str] = []
        frontmatter_done = False
        for line in filtered:
            if not frontmatter_done:
                if _detect_chapter(line) is not None or _is_verse_candidate(line):
                    frontmatter_done = True
                    cleaned.append(line)
                    continue
                if _is_frontmatter_line(line):
                    stats["lines_frontmatter_dropped"] += 1
                    continue
            cleaned.append(line)
        filtered = cleaned

    if filter_ocr_noise:
        cleaned = []
        for line in filtered:
            if _detect_chapter(line) is not None:
                cleaned.append(line)
                continue
            if len(line.strip()) < 4:
                cleaned.append(line)
                continue
            if _noise_score(line) >= noise_threshold:
                stats["lines_noise_dropped"] += 1
                continue
            cleaned.append(line)
        filtered = cleaned

    return filtered, stats


def _split_verses(lines: List[str]) -> List[str]:
    verses: List[str] = []
    buffer: List[str] = []

    for line in lines:
        if not line.strip():
            if buffer:
                verses.append(_normalize_text(" ".join(buffer)))
                buffer = []
            continue

        buffer.append(line.strip())

    if buffer:
        verses.append(_normalize_text(" ".join(buffer)))

    return verses


def _parse_plain(
    files: List[Path],
    *,
    chaptered: bool,
    filter_frontmatter: bool,
    filter_ocr_noise: bool,
    frontmatter_max_lines: int,
    noise_threshold: float,
) -> Tuple[List[Tuple[Optional[int], str]], Dict[str, int]]:
    entries: List[Tuple[Optional[int], str]] = []
    current_chapter: Optional[int] = None
    stats = {
        "lines_scanned": 0,
        "lines_frontmatter_dropped": 0,
        "lines_noise_dropped": 0,
    }

    for path in files:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        filtered, file_stats = _filter_lines(
            lines,
            filter_frontmatter=filter_frontmatter,
            filter_ocr_noise=filter_ocr_noise,
            frontmatter_max_lines=frontmatter_max_lines,
            noise_threshold=noise_threshold,
        )
        for key in stats:
            stats[key] += file_stats.get(key, 0)

        if chaptered:
            buffer: List[str] = []
            for line in filtered:
                chapter = _detect_chapter(line)
                if chapter is not None:
                    if buffer:
                        verses = _split_verses(buffer)
                        entries.extend([(current_chapter, v) for v in verses])
                        buffer = []
                    current_chapter = chapter
                    continue
                buffer.append(line)
            if buffer:
                verses = _split_verses(buffer)
                entries.extend([(current_chapter, v) for v in verses])
        else:
            verses = _split_verses(filtered)
            entries.extend([(None, v) for v in verses])

    return entries, stats


def _build_yaml(entries: List[Tuple[Optional[int], str]], collection_key: str, chaptered: bool) -> Dict[str, Dict[str, str]]:
    output: Dict[str, Dict[str, str]] = {}

    if chaptered:
        chapter_counts: Dict[int, int] = {}
        for chapter, text in entries:
            chapter_num = chapter if chapter is not None else 1
            chapter_counts.setdefault(chapter_num, 0)
            chapter_counts[chapter_num] += 1
            verse_num = chapter_counts[chapter_num]
            key = f"chapter-{chapter_num:02d}-shloka-{verse_num:02d}"
            output[key] = {"devanagari": text}
    else:
        for idx, (_, text) in enumerate(entries, start=1):
            key = f"verse-{idx:02d}"
            output[key] = {"devanagari": text}

    if not output:
        raise ValueError("No verses detected. Check input files or format.")

    return output


def _render_yaml(data: Dict[str, Dict[str, str]]) -> str:
    return yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Parse canonical source text into data/verses/<collection>.yaml",
    )
    parser.add_argument("--collection", required=True, help="Collection key (e.g., hanuman-chalisa)")
    parser.add_argument("--source", action="append", help="Source file path (repeatable)")
    parser.add_argument("--source-dir", help="Directory containing source files")
    parser.add_argument("--source-glob", default="**/*.txt", help="Glob for source files under --source-dir")
    parser.add_argument("--format", default="devanagari-plain", choices=["devanagari-plain", "chaptered-plain"])
    parser.add_argument("--output", help="Output YAML path (default: data/verses/<collection>.yaml)")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing output")
    parser.add_argument("--diff", action="store_true", help="Show unified diff if output changes")
    parser.add_argument("--filter-frontmatter", default="true", choices=["true", "false"])
    parser.add_argument("--filter-ocr-noise", default="true", choices=["true", "false"])
    parser.add_argument("--frontmatter-max-lines", type=int, default=300)
    parser.add_argument("--noise-threshold", type=float, default=0.65)
    parser.add_argument("--report", help="Write parse report JSON to this path")

    args = parser.parse_args()

    try:
        files = _collect_files(args.source, args.source_dir, args.source_glob)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    chaptered = args.format == "chaptered-plain"
    filter_frontmatter = args.filter_frontmatter.lower() == "true"
    filter_ocr_noise = args.filter_ocr_noise.lower() == "true"

    entries, stats = _parse_plain(
        files,
        chaptered=chaptered,
        filter_frontmatter=filter_frontmatter,
        filter_ocr_noise=filter_ocr_noise,
        frontmatter_max_lines=args.frontmatter_max_lines,
        noise_threshold=args.noise_threshold,
    )
    data = _build_yaml(entries, args.collection, chaptered=chaptered)
    rendered = _render_yaml(data)

    output_path = Path(args.output) if args.output else Path("data") / "verses" / f"{args.collection}.yaml"
    existing = output_path.read_text(encoding="utf-8") if output_path.exists() else None

    if args.diff and existing is not None and existing != rendered:
        diff = difflib.unified_diff(
            existing.splitlines(),
            rendered.splitlines(),
            fromfile=str(output_path),
            tofile=str(output_path),
            lineterm="",
        )
        print("\n".join(diff))

    total = len(data)
    print(f"Parsed {total} verses from {len(files)} file(s).")
    print(f"Lines scanned: {stats['lines_scanned']}")
    print(f"Front-matter lines dropped: {stats['lines_frontmatter_dropped']}")
    print(f"OCR/noise lines dropped: {stats['lines_noise_dropped']}")
    print(f"Output: {output_path}")

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "collection": args.collection,
            "files": [str(p) for p in files],
            "format": args.format,
            "filter_frontmatter": filter_frontmatter,
            "filter_ocr_noise": filter_ocr_noise,
            "frontmatter_max_lines": args.frontmatter_max_lines,
            "noise_threshold": args.noise_threshold,
            "verses": total,
            "lines_scanned": stats["lines_scanned"],
            "lines_frontmatter_dropped": stats["lines_frontmatter_dropped"],
            "lines_noise_dropped": stats["lines_noise_dropped"],
        }
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote report: {report_path}")

    if args.dry_run:
        print("Dry run: no files written.")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if existing == rendered:
        print("No changes detected; output is up to date.")
        return

    output_path.write_text(rendered, encoding="utf-8")
    print("Wrote canonical YAML.")


if __name__ == "__main__":
    main()

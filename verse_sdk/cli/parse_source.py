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
    re.compile(r"\bChapter\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"\bअध्याय\s+(\d+)\b"),
    re.compile(r"\bअध्यायः\s+(\d+)\b"),
    re.compile(r"(?:अ)?ऽ?ध्याय[:ः।]?\s*[-–—]?\s*([०-९0-9]+)"),
    # Devanagari ordinal heading styles like: "०.१. प्रथमोऽध्यायः ..."
    re.compile(r"^\s*[०-९0-9]+\s*[.\-]\s*([०-९0-9]+)\s*[.\-]\s*.*(?:अ)?ऽ?ध्याय"),
    re.compile(r"^\s*([०-९0-9]+)\s*[.\-]\s*.*(?:अ)?ऽ?ध्याय"),
    re.compile(r"[०-९0-9]+\s*[.\-]\s*([०-९0-9]+)\s*[.\-].*(?:अ)?ऽ?ध्याय"),
]

FRONTMATTER_PATTERNS = [
    re.compile(r"\b(publisher|publication|press|edition|copyright|isbn)\b", re.IGNORECASE),
    re.compile(r"\b(all rights reserved|printed in|published by)\b", re.IGNORECASE),
    re.compile(r"\b(preface|foreword|introduction|table of contents|contents)\b", re.IGNORECASE),
]

SCAFFOLD_COMMENT_PATTERNS = [
    re.compile(r"^\s*#"),
    re.compile(r"\bsource text for\b", re.IGNORECASE),
    re.compile(r"\bpaste canonical plain-text\b", re.IGNORECASE),
    re.compile(r"\bthen run\b", re.IGNORECASE),
    re.compile(r"\bverse-parse-source\b", re.IGNORECASE),
]

VALID_CHAR_PATTERN = re.compile(r"[\u0900-\u097F\u0966-\u096F\w\s\.,;:'\"()\[\]\-—–!?/]+")

PROFILE_DEFAULTS = {
    "default": {
        "min_devanagari": 6,
        "require_danda": False,
        "drop_prose": False,
        "prose_max_words": 28,
        "extra_frontmatter_patterns": [],
    },
    "srimad-bhagavat": {
        "min_devanagari": 10,
        "require_danda": True,
        "drop_prose": True,
        "prose_max_words": 18,
        "noise_threshold": 0.55,
        "frontmatter_max_lines": 500,
        "start_markers": [
            "श्रीमदभागवत-माहात्म्य",
            "श्रीमद्भागवत-माहात्म्य",
            "श्रीमद भागवत-माहात्म्य",
        ],
        "drop_heading_lines": True,
        "heading_patterns": [
            re.compile(r"^\s*॥\s*ॐ\s*नमो\s*भगवते\s*वासुदेवाय\s*॥\s*$"),
            re.compile(r"^\s*कृष्णं\s+नारायणं.+पृथासुतम्\s*॥\s*$"),
            re.compile(r".*अध्यायः.*"),
            re.compile(r".*अध्याय.*"),
        ],
        "chapter_scope": "file",
        "canto_regex": r"canto-(\d+)",
        "extra_frontmatter_patterns": [
            re.compile(r"\b(edition|press|publisher|publication)\b", re.IGNORECASE),
            re.compile(r"\b(email|website|www\.|http)\b", re.IGNORECASE),
            re.compile(r"\b(phone|mobile|whatsapp|fax)\b", re.IGNORECASE),
            re.compile(r"\b(address|printed at|printed by)\b", re.IGNORECASE),
        ],
    },
}


AUTO_SOURCE_GLOB = "**/*.txt"


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


def _auto_discover_source_inputs(collection: str, project_dir: Path = Path.cwd()) -> Tuple[Optional[List[str]], Optional[str], str, List[str]]:
    """
    Auto-discover parse sources for a collection.

    Discovery order:
    1. data/sources/<collection>.txt
    2. data/sources/<collection>/ (with default glob)
    """
    source_file = project_dir / "data" / "sources" / f"{collection}.txt"
    source_dir = project_dir / "data" / "sources" / collection
    notices: List[str] = []

    if source_file.exists() and source_dir.exists():
        notices.append(
            f"Notice: found both {source_file} and {source_dir}; preferring file input."
        )

    if source_file.exists():
        return [str(source_file)], None, AUTO_SOURCE_GLOB, notices

    if source_dir.exists():
        return None, str(source_dir), AUTO_SOURCE_GLOB, notices

    raise FileNotFoundError(
        "No source input found.\n"
        f"Tried:\n"
        f"  - {source_file}\n"
        f"  - {source_dir}/\n"
        "Provide --source/--source-dir explicitly, or place source text in one of those locations."
    )


def _detect_chapter(line: str) -> Optional[int]:
    for pattern in CHAPTER_PATTERNS:
        match = pattern.search(line)
        if match:
            value = match.group(1)
            trans = str.maketrans("०१२३४५६७८९", "0123456789")
            return int(value.translate(trans))
    return None


def _contains_chapter_markers(files: List[Path], min_hits: int = 1) -> bool:
    """Return True if chapter markers are detected in the given source files."""
    hits = 0
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for line in lines:
            if _detect_chapter(line) is not None:
                hits += 1
                if hits >= min_hits:
                    return True
    return False


def _is_frontmatter_line(line: str, profile: dict) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if any(pattern.search(stripped) for pattern in SCAFFOLD_COMMENT_PATTERNS):
        return True
    patterns = FRONTMATTER_PATTERNS + profile.get("extra_frontmatter_patterns", [])
    return any(pattern.search(stripped) for pattern in patterns)


def _noise_score(line: str) -> float:
    if not line.strip():
        return 0.0
    total = len(line)
    valid = len("".join(VALID_CHAR_PATTERN.findall(line)))
    if total == 0:
        return 0.0
    return 1.0 - (valid / total)


def _is_verse_candidate(line: str, profile: dict) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    # Do not treat scaffold/frontmatter/comment lines as verse candidates.
    if _is_frontmatter_line(stripped, profile):
        return False
    devanagari_chars = len(re.findall(r"[\u0900-\u097F]", stripped))
    min_devanagari = profile.get("min_devanagari", 6)
    if devanagari_chars >= min_devanagari:
        if profile.get("require_danda"):
            return "।" in stripped or "॥" in stripped
        return True
    letters = len(re.findall(r"[A-Za-z]", stripped))
    return letters >= 12


def _is_prose_line(line: str, profile: dict) -> bool:
    if not profile.get("drop_prose"):
        return False
    stripped = line.strip()
    if not stripped:
        return False
    if "।" in stripped or "॥" in stripped:
        return False
    words = stripped.split()
    return len(words) >= profile.get("prose_max_words", 28)


def _is_heading_line(line: str, profile: dict) -> bool:
    if not profile.get("drop_heading_lines"):
        return False
    stripped = line.strip()
    if not stripped:
        return False
    patterns = profile.get("heading_patterns", [])
    return any(pattern.search(stripped) for pattern in patterns)


def _filter_lines(
    lines: List[str],
    *,
    filter_frontmatter: bool,
    filter_ocr_noise: bool,
    frontmatter_max_lines: int,
    noise_threshold: float,
    profile: dict,
    start_marker: Optional[str],
    start_marker_regex: Optional[re.Pattern[str]],
    disable_start_anchor: bool,
) -> Tuple[List[str], Dict[str, int]]:
    stats = {
        "lines_scanned": len(lines),
        "lines_frontmatter_dropped": 0,
        "lines_noise_dropped": 0,
        "lines_prose_dropped": 0,
        "lines_heading_dropped": 0,
        "start_anchor_found": 0,
    }
    samples = {
        "frontmatter": [],
        "noise": [],
        "prose": [],
        "heading": [],
    }

    filtered = lines[:]
    anchor_info = {
        "anchor_found": False,
        "anchor_value": None,
        "anchor_line": None,
    }

    if not disable_start_anchor:
        markers: List[str] = []
        if start_marker:
            markers = [start_marker]
        else:
            markers = profile.get("start_markers", []) or []

        if start_marker_regex is not None:
            for idx, line in enumerate(filtered):
                if start_marker_regex.search(line):
                    anchor_info["anchor_found"] = True
                    anchor_info["anchor_value"] = start_marker_regex.pattern
                    anchor_info["anchor_line"] = idx + 1
                    filtered = filtered[idx:]
                    break
        elif markers:
            for idx, line in enumerate(filtered):
                if any(marker in line for marker in markers):
                    anchor_info["anchor_found"] = True
                    anchor_info["anchor_value"] = next(m for m in markers if m in line)
                    anchor_info["anchor_line"] = idx + 1
                    filtered = filtered[idx:]
                    break

        if anchor_info["anchor_found"]:
            stats["start_anchor_found"] = 1

    if filter_frontmatter:
        scan_limit = min(frontmatter_max_lines, len(filtered))
        first_content_idx = None
        for idx in range(scan_limit):
            line = filtered[idx]
            if _detect_chapter(line) is not None or _is_verse_candidate(line, profile):
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
                if _detect_chapter(line) is not None or _is_verse_candidate(line, profile):
                    frontmatter_done = True
                    cleaned.append(line)
                    continue
                if _is_frontmatter_line(line, profile):
                    stats["lines_frontmatter_dropped"] += 1
                    if len(samples["frontmatter"]) < 5:
                        samples["frontmatter"].append(line.strip())
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
                if len(samples["noise"]) < 5:
                    samples["noise"].append(line.strip())
                continue
            cleaned.append(line)
        filtered = cleaned

    if profile.get("drop_prose"):
        cleaned = []
        for line in filtered:
            if _is_prose_line(line, profile):
                stats["lines_prose_dropped"] += 1
                if len(samples["prose"]) < 5:
                    samples["prose"].append(line.strip())
                continue
            cleaned.append(line)
        filtered = cleaned

    if profile.get("drop_heading_lines"):
        cleaned = []
        for line in filtered:
            if _is_heading_line(line, profile):
                stats["lines_heading_dropped"] += 1
                if len(samples["heading"]) < 5:
                    samples["heading"].append(line.strip())
                continue
            cleaned.append(line)
        filtered = cleaned

    return filtered, {**stats, "samples": samples, "anchor": anchor_info}


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
    profile: dict,
    start_marker: Optional[str],
    start_marker_regex: Optional[re.Pattern[str]],
    disable_start_anchor: bool,
    chapter_scope: str,
    canto_regex: Optional[re.Pattern[str]],
) -> Tuple[List[Tuple[Optional[int], Optional[int], str]], Dict[str, int]]:
    entries: List[Tuple[Optional[int], Optional[int], str]] = []
    stats: Dict[str, int] = {
        "lines_scanned": 0,
        "lines_frontmatter_dropped": 0,
        "lines_noise_dropped": 0,
        "lines_prose_dropped": 0,
    }
    samples: Dict[str, List[str]] = {}
    anchor_info = {
        "anchor_found": False,
        "anchor_value": None,
        "anchor_line": None,
    }

    for path in files:
        current_chapter: Optional[int] = None
        canto_value: Optional[int] = None
        if canto_regex:
            match = canto_regex.search(path.name)
            if match:
                trans = str.maketrans("०१२३४५६७८९", "0123456789")
                canto_value = int(match.group(1).translate(trans))
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        filtered, file_stats = _filter_lines(
            lines,
            filter_frontmatter=filter_frontmatter,
            filter_ocr_noise=filter_ocr_noise,
            frontmatter_max_lines=frontmatter_max_lines,
            noise_threshold=noise_threshold,
            profile=profile,
            start_marker=start_marker,
            start_marker_regex=start_marker_regex,
            disable_start_anchor=disable_start_anchor,
        )
        for key in list(stats.keys()):
            stats[key] += int(file_stats.get(key, 0))
        for sample_key, sample_values in file_stats.get("samples", {}).items():
            samples.setdefault(sample_key, [])
            for value in sample_values:
                if len(samples[sample_key]) < 5:
                    samples[sample_key].append(value)

        if file_stats.get("anchor", {}).get("anchor_found") and not anchor_info["anchor_found"]:
            anchor_info = file_stats["anchor"]

        if chaptered:
            buffer: List[str] = []
            for line in filtered:
                chapter = _detect_chapter(line)
                if chapter is not None:
                    if buffer:
                        verses = _split_verses(buffer)
                        entries.extend([(canto_value, current_chapter, v) for v in verses])
                        buffer = []
                    if chapter_scope == "file" and current_chapter is not None and chapter < current_chapter:
                        current_chapter = chapter
                    else:
                        current_chapter = chapter
                    continue
                buffer.append(line)
            if buffer:
                verses = _split_verses(buffer)
                entries.extend([(canto_value, current_chapter, v) for v in verses])
        else:
            verses = _split_verses(filtered)
            entries.extend([(canto_value, None, v) for v in verses])

    return entries, {**stats, "samples": samples, "anchor": anchor_info}


def _build_yaml(entries: List[Tuple[Optional[int], Optional[int], str]], collection_key: str, chaptered: bool) -> Dict[str, Dict[str, str]]:
    output: Dict[str, Dict[str, str]] = {}

    if chaptered:
        chapter_counts: Dict[Tuple[Optional[int], int], int] = {}
        for canto, chapter, text in entries:
            chapter_num = chapter if chapter is not None else 1
            key_scope = (canto, chapter_num)
            chapter_counts.setdefault(key_scope, 0)
            chapter_counts[key_scope] += 1
            verse_num = chapter_counts[key_scope]
            if canto is not None:
                key = f"canto-{canto:02d}-chapter-{chapter_num:02d}-shloka-{verse_num:02d}"
            else:
                key = f"chapter-{chapter_num:02d}-shloka-{verse_num:02d}"
            output[key] = {"devanagari": text}
    else:
        for idx, (canto, _, text) in enumerate(entries, start=1):
            if canto is not None:
                key = f"canto-{canto:02d}-verse-{idx:02d}"
            else:
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
    parser.add_argument("--profile", default="default", choices=list(PROFILE_DEFAULTS.keys()))
    parser.add_argument("--output", help="Output YAML path (default: data/verses/<collection>.yaml)")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing output")
    parser.add_argument("--diff", action="store_true", help="Show unified diff if output changes")
    parser.add_argument("--filter-frontmatter", default="true", choices=["true", "false"])
    parser.add_argument("--filter-ocr-noise", default="true", choices=["true", "false"])
    parser.add_argument("--frontmatter-max-lines", type=int, default=300)
    parser.add_argument("--noise-threshold", type=float, default=0.65)
    parser.add_argument("--report", help="Write parse report JSON to this path")
    parser.add_argument("--expected-count-min", type=int, help="Warn if parsed verses drop below this count")
    parser.add_argument("--expected-count-max", type=int, help="Warn if parsed verses exceed this count")
    parser.add_argument("--start-marker", help="Start parsing after this marker string")
    parser.add_argument("--start-marker-regex", help="Start parsing after regex match")
    parser.add_argument("--disable-start-anchor", action="store_true", help="Disable profile start-anchor behavior")
    parser.add_argument("--disable-heading-filter", action="store_true", help="Disable profile heading-line filter")
    parser.add_argument("--chapter-scope", choices=["global", "file"], default="global", help="Chapter numbering scope (default: global)")
    parser.add_argument("--canto-regex", help="Regex to extract canto number from filename")

    args = parser.parse_args()

    def _arg_provided(flag: str) -> bool:
        return any(arg == flag or arg.startswith(flag + "=") for arg in sys.argv[1:])

    source = args.source
    source_dir = args.source_dir
    source_glob = args.source_glob
    source_mode = "explicit"

    if not source and not source_dir:
        try:
            source, source_dir, source_glob, notices = _auto_discover_source_inputs(args.collection, Path.cwd())
        except FileNotFoundError as exc:
            print(f"Error: {exc}")
            sys.exit(1)

        source_mode = "auto-discovered"
        for notice in notices:
            print(notice)

        if _arg_provided("--source-glob"):
            print(
                f"Note: --source-glob is only used with explicit --source-dir; "
                f"using default auto-discovery glob '{AUTO_SOURCE_GLOB}'."
            )

    try:
        files = _collect_files(source, source_dir, source_glob)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    if source:
        print(f"Using source file input ({source_mode}): {', '.join(str(Path(p)) for p in source)}")
    elif source_dir:
        print(f"Using source directory input ({source_mode}): {source_dir} (glob: {source_glob})")
        print(f"Matched {len(files)} file(s).")

    chaptered = args.format == "chaptered-plain"
    if not _arg_provided("--format") and args.format == "devanagari-plain":
        if _contains_chapter_markers(files):
            chaptered = True
            print("Detected chapter markers in source; using chaptered-plain format.")

    profile = PROFILE_DEFAULTS.get(args.profile, PROFILE_DEFAULTS["default"])

    if not _arg_provided("--noise-threshold") and "noise_threshold" in profile:
        args.noise_threshold = profile["noise_threshold"]
    if not _arg_provided("--frontmatter-max-lines") and "frontmatter_max_lines" in profile:
        args.frontmatter_max_lines = profile["frontmatter_max_lines"]
    if not _arg_provided("--chapter-scope") and "chapter_scope" in profile:
        args.chapter_scope = profile["chapter_scope"]
    if not _arg_provided("--canto-regex") and "canto_regex" in profile:
        args.canto_regex = profile["canto_regex"]

    filter_frontmatter = args.filter_frontmatter.lower() == "true"
    filter_ocr_noise = args.filter_ocr_noise.lower() == "true"

    start_marker_regex = re.compile(args.start_marker_regex) if args.start_marker_regex else None
    canto_regex = re.compile(args.canto_regex) if args.canto_regex else None

    if args.disable_heading_filter:
        profile = {**profile, "drop_heading_lines": False}

    entries, stats = _parse_plain(
        files,
        chaptered=chaptered,
        filter_frontmatter=filter_frontmatter,
        filter_ocr_noise=filter_ocr_noise,
        frontmatter_max_lines=args.frontmatter_max_lines,
        noise_threshold=args.noise_threshold,
        profile=profile,
        start_marker=args.start_marker,
        start_marker_regex=start_marker_regex,
        disable_start_anchor=args.disable_start_anchor,
        chapter_scope=args.chapter_scope,
        canto_regex=canto_regex,
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
    print(f"Prose/commentary lines dropped: {stats.get('lines_prose_dropped', 0)}")
    print(f"Heading lines dropped: {stats.get('lines_heading_dropped', 0)}")
    if stats.get("anchor", {}).get("anchor_found"):
        print(f"Start anchor: {stats['anchor'].get('anchor_value')} (line {stats['anchor'].get('anchor_line')})")
    else:
        print("Start anchor: not found")
    print(f"Output: {output_path}")

    if args.expected_count_min and total < args.expected_count_min:
        print(f"Warning: parsed verse count {total} is below expected minimum {args.expected_count_min}")
    if args.expected_count_max and total > args.expected_count_max:
        print(f"Warning: parsed verse count {total} exceeds expected maximum {args.expected_count_max}")

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "collection": args.collection,
            "files": [str(p) for p in files],
            "format": args.format,
            "profile": args.profile,
            "filter_frontmatter": filter_frontmatter,
            "filter_ocr_noise": filter_ocr_noise,
            "frontmatter_max_lines": args.frontmatter_max_lines,
            "noise_threshold": args.noise_threshold,
            "verses": total,
            "lines_scanned": stats["lines_scanned"],
            "lines_frontmatter_dropped": stats["lines_frontmatter_dropped"],
            "lines_noise_dropped": stats["lines_noise_dropped"],
            "lines_prose_dropped": stats.get("lines_prose_dropped", 0),
            "lines_heading_dropped": stats.get("lines_heading_dropped", 0),
            "samples": stats.get("samples", {}),
            "start_anchor": stats.get("anchor", {}),
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

"""Tests for source input resolution in verse_sdk/cli/parse_source.py."""

import pytest

from verse_sdk.cli.parse_source import (
    PROFILE_DEFAULTS,
    _auto_discover_source_inputs,
    _build_yaml,
    _contains_chapter_markers,
    _detect_chapter,
    _filter_lines,
    _parse_plain,
)


def test_auto_discover_prefers_collection_file(tmp_path):
    sources_dir = tmp_path / "data" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    source_file = sources_dir / "shiv-puran.txt"
    source_file.write_text("verse text", encoding="utf-8")

    source, source_dir, source_glob, notices = _auto_discover_source_inputs("shiv-puran", tmp_path)

    assert source == [str(source_file)]
    assert source_dir is None
    assert source_glob == "**/*.txt"
    assert notices == []


def test_auto_discover_uses_collection_directory_when_file_missing(tmp_path):
    source_dir_path = tmp_path / "data" / "sources" / "shiv-puran"
    source_dir_path.mkdir(parents=True, exist_ok=True)
    (source_dir_path / "part-01.txt").write_text("verse text", encoding="utf-8")

    source, source_dir, source_glob, notices = _auto_discover_source_inputs("shiv-puran", tmp_path)

    assert source is None
    assert source_dir == str(source_dir_path)
    assert source_glob == "**/*.txt"
    assert notices == []


def test_auto_discover_prefers_file_when_both_exist(tmp_path):
    sources_dir = tmp_path / "data" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    source_file = sources_dir / "shiv-puran.txt"
    source_file.write_text("verse text", encoding="utf-8")
    source_dir_path = sources_dir / "shiv-puran"
    source_dir_path.mkdir(parents=True, exist_ok=True)
    (source_dir_path / "part-01.txt").write_text("verse text", encoding="utf-8")

    source, source_dir, source_glob, notices = _auto_discover_source_inputs("shiv-puran", tmp_path)

    assert source == [str(source_file)]
    assert source_dir is None
    assert source_glob == "**/*.txt"
    assert len(notices) == 1
    assert "preferring file input" in notices[0]


def test_auto_discover_raises_when_no_default_source_exists(tmp_path):
    with pytest.raises(FileNotFoundError) as exc:
        _auto_discover_source_inputs("shiv-puran", tmp_path)

    msg = str(exc.value)
    assert "No source input found." in msg
    assert "data/sources/shiv-puran.txt" in msg
    assert "data/sources/shiv-puran/" in msg


def test_detect_chapter_from_devanagari_ordinal_headings():
    assert _detect_chapter("०.१. प्रथमोऽध्यायः । तन्महिमवर्णनम् ।") == 1
    assert _detect_chapter("०.२. द्वितीयोऽध्यायः ।") == 2
    assert _detect_chapter("श्रीशिवमहापुराणमाहात्म्यम् ०.१. प्रथमोऽध्यायः । तन्महिमवर्णनम् ।") == 1


def test_filter_lines_drops_scaffold_comment_preamble():
    lines = [
        "# Source text for shiv-puran",
        "# Paste canonical plain-text verses here (UTF-8).",
        "# Then run:",
        "#   verse-parse-source --collection shiv-puran",
        "",
        "श्रीशिवमहापुराणमाहात्म्यम् ०.१. प्रथमोऽध्यायः । तन्महिमवर्णनम् ।",
    ]

    filtered, stats = _filter_lines(
        lines,
        filter_frontmatter=True,
        filter_ocr_noise=False,
        frontmatter_max_lines=300,
        noise_threshold=0.65,
        profile=PROFILE_DEFAULTS["default"],
        start_marker=None,
        start_marker_regex=None,
        disable_start_anchor=True,
    )

    assert filtered
    assert filtered[0] == "श्रीशिवमहापुराणमाहात्म्यम् ०.१. प्रथमोऽध्यायः । तन्महिमवर्णनम् ।"
    assert all(not line.strip().startswith("#") for line in filtered)
    assert stats["lines_frontmatter_dropped"] >= 4


def test_contains_chapter_markers_detects_inline_ordinal_pattern(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text(
        "श्रीशिवमहापुराणमाहात्म्यम् ०.१. प्रथमोऽध्यायः । तन्महिमवर्णनम् ।\n",
        encoding="utf-8",
    )
    assert _contains_chapter_markers([source]) is True


def test_contains_chapter_markers_returns_false_when_absent(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("ॐ नमः शिवाय ।\nशिवोऽहम् ।\n", encoding="utf-8")
    assert _contains_chapter_markers([source]) is False


def test_default_mode_auto_switches_to_chaptered_when_markers_present(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text(
        "०.१. प्रथमोऽध्यायः । तन्महिमवर्णनम् ।\n"
        "शौनक उवाच । हे हे सूत महाप्राज्ञ ।\n"
        "\n"
        "०.२. द्वितीयोऽध्यायः ।\n"
        "सूत उवाच । श्रुणु मुनिश्रेष्ठ ।\n",
        encoding="utf-8",
    )

    files = [source]
    chaptered = False
    if _contains_chapter_markers(files):
        chaptered = True

    entries, _stats = _parse_plain(
        files,
        chaptered=chaptered,
        filter_frontmatter=True,
        filter_ocr_noise=False,
        frontmatter_max_lines=300,
        noise_threshold=0.65,
        profile=PROFILE_DEFAULTS["default"],
        start_marker=None,
        start_marker_regex=None,
        disable_start_anchor=True,
        chapter_scope="global",
        canto_regex=None,
    )
    data = _build_yaml(entries, "shiv-puran", chaptered=chaptered)

    keys = list(data.keys())
    assert any(k.startswith("chapter-01-") for k in keys)
    assert any(k.startswith("chapter-02-") for k in keys)


def test_chaptered_parsing_drops_title_preamble_before_first_chapter(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text(
        "श्रीशिवमहापुराणमाहात्म्यम्\n"
        "०.१. प्रथमोऽध्यायः । तन्महिमवर्णनम् ।\n"
        "शौनक उवाच । हे हे सूत महाप्राज्ञ ।\n",
        encoding="utf-8",
    )

    entries, _stats = _parse_plain(
        [source],
        chaptered=True,
        filter_frontmatter=True,
        filter_ocr_noise=False,
        frontmatter_max_lines=300,
        noise_threshold=0.65,
        profile=PROFILE_DEFAULTS["default"],
        start_marker=None,
        start_marker_regex=None,
        disable_start_anchor=True,
        chapter_scope="global",
        canto_regex=None,
    )
    data = _build_yaml(entries, "shiv-puran", chaptered=True)

    first_key = next(iter(data))
    assert first_key == "chapter-01-shloka-01"
    assert data[first_key]["devanagari"] == "शौनक उवाच । हे हे सूत महाप्राज्ञ ।"

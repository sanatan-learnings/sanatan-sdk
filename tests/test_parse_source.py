"""Tests for source input resolution in verse_sdk/cli/parse_source.py."""

import pytest

from verse_sdk.cli.parse_source import _auto_discover_source_inputs, _detect_chapter


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

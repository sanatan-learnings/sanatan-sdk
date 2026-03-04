"""Tests for verse_sdk/cli/add.py."""

from pathlib import Path

import yaml

from verse_sdk.cli.add import add_verses_to_yaml, sync_collection_total_verses


def _write_collections(project_dir: Path, total_verses: str = "3") -> None:
    data_dir = project_dir / "_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "collections.yml").write_text(
        f"""# Collection registry
hanuman-chalisa:
  enabled: true
  name:
    en: "Hanuman Chalisa"
  subdirectory: "hanuman-chalisa"
  permalink_base: "/hanuman-chalisa"
  total_verses: {total_verses}
""",
        encoding="utf-8",
    )


def _write_canonical(project_dir: Path, count: int) -> None:
    verses_dir = project_dir / "data" / "verses"
    verses_dir.mkdir(parents=True, exist_ok=True)
    data = {"_meta": {"collection": "hanuman-chalisa"}}
    for i in range(1, count + 1):
        data[f"verse-{i:02d}"] = {"devanagari": ""}
    (verses_dir / "hanuman-chalisa.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_sync_collection_total_verses_updates_existing_value(tmp_path):
    _write_collections(tmp_path, total_verses="3")

    changed, old_value, new_value = sync_collection_total_verses(tmp_path, "hanuman-chalisa", 5)

    assert changed is True
    assert old_value == 3
    assert new_value == 5
    content = (tmp_path / "_data" / "collections.yml").read_text(encoding="utf-8")
    assert "total_verses: 5" in content
    assert "# Collection registry" in content


def test_sync_collection_total_verses_inserts_missing_field(tmp_path):
    _write_collections(tmp_path, total_verses="'[placeholder]'")

    changed, old_value, new_value = sync_collection_total_verses(tmp_path, "hanuman-chalisa", 4)

    assert changed is True
    assert old_value is None
    assert new_value == 4
    content = (tmp_path / "_data" / "collections.yml").read_text(encoding="utf-8")
    assert "total_verses: 4" in content


def test_add_verses_returns_updated_canonical_total(tmp_path):
    _write_collections(tmp_path, total_verses="3")
    _write_canonical(tmp_path, count=3)

    added, skipped, _format_used, total = add_verses_to_yaml(
        tmp_path,
        "hanuman-chalisa",
        [4, 5],
        collection_info={"enabled": True},
    )

    assert added == 2
    assert skipped == 0
    assert total == 5

"""Tests for verse_sdk/cli/init.py — project scaffolding."""

from pathlib import Path

from verse_sdk.cli.init import (
    create_directory_structure,
    create_example_collection,
    create_template_files,
    init_project,
)

# ---------------------------------------------------------------------------
# create_directory_structure
# ---------------------------------------------------------------------------

def test_creates_required_dirs(tmp_path):
    create_directory_structure(tmp_path)
    for d in ["_data", "_verses", "data/themes", "data/verses", "data/scenes"]:
        assert (tmp_path / d).is_dir(), f"Missing required dir: {d}"


def test_creates_optional_dirs_by_default(tmp_path):
    create_directory_structure(tmp_path, minimal=False)
    for d in ["images", "audio", "data/sources", "data/puranic-index", "data/embeddings"]:
        assert (tmp_path / d).is_dir(), f"Missing optional dir: {d}"


def test_minimal_skips_optional_dirs(tmp_path):
    create_directory_structure(tmp_path, minimal=True)
    for d in ["images", "audio", "data/sources", "data/puranic-index", "data/embeddings"]:
        assert not (tmp_path / d).exists(), f"Unexpected dir in minimal mode: {d}"


def test_idempotent(tmp_path):
    create_directory_structure(tmp_path)
    create_directory_structure(tmp_path)  # second call should not raise


# ---------------------------------------------------------------------------
# create_template_files
# ---------------------------------------------------------------------------

def test_creates_required_files(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "my-project")
    for f in [
        ".env.example",
        "_data/collections.yml",
        "_data/verse-config.yml",
        ".gitignore",
        "Gemfile",
        "_config.yml",
        "index.md",
        "README.md",
    ]:
        assert (tmp_path / f).exists(), f"Missing file: {f}"


def test_readme_contains_project_name(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "awesome-project")
    readme = (tmp_path / "README.md").read_text()
    assert "awesome-project" in readme


def test_does_not_overwrite_existing_files(tmp_path):
    create_directory_structure(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_text("original content")
    create_template_files(tmp_path, "my-project")
    assert readme.read_text() == "original content"


def test_verse_config_contains_defaults_section(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "my-project")
    content = (tmp_path / "_data" / "verse-config.yml").read_text()
    assert "defaults" in content


def test_gitignore_excludes_env(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "my-project")
    content = (tmp_path / ".gitignore").read_text()
    assert ".env" in content


def test_env_example_includes_hf_token(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "my-project")
    content = (tmp_path / ".env.example").read_text()
    assert "HF_TOKEN=" in content
    assert "https://huggingface.co/settings/tokens" in content


def test_gemfile_includes_jekyll(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "my-project")
    content = (tmp_path / "Gemfile").read_text()
    assert 'gem "jekyll"' in content


def test_index_page_has_jekyll_frontmatter(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "my-project")
    content = (tmp_path / "index.md").read_text()
    assert content.startswith("---\n")
    assert "layout: default" in content


# ---------------------------------------------------------------------------
# create_example_collection
# ---------------------------------------------------------------------------

def test_creates_verse_files(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "hanuman-chalisa", num_verses=3)
    for i in range(1, 4):
        f = tmp_path / "_verses" / "hanuman-chalisa" / f"verse-{i:02d}.md"
        assert f.exists(), f"Missing: {f.name}"


def test_creates_canonical_yaml(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "hanuman-chalisa", num_verses=2)
    yaml_file = tmp_path / "data" / "verses" / "hanuman-chalisa.yaml"
    assert yaml_file.exists()
    assert "hanuman-chalisa" in yaml_file.read_text()


def test_creates_theme_file(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "hanuman-chalisa", num_verses=1)
    theme = tmp_path / "data" / "themes" / "hanuman-chalisa" / "modern-minimalist.yml"
    assert theme.exists()


def test_creates_scenes_file(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "hanuman-chalisa", num_verses=2)
    scenes = tmp_path / "data" / "scenes" / "hanuman-chalisa.yml"
    assert scenes.exists()


def test_creates_source_text_placeholder_file(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "hanuman-chalisa", num_verses=2)
    source = tmp_path / "data" / "sources" / "hanuman-chalisa.txt"
    assert source.exists()
    assert "verse-parse-source --collection hanuman-chalisa" in source.read_text()


def test_adds_collection_to_collections_yml(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "sundar-kaand", num_verses=2)
    content = (tmp_path / "_data" / "collections.yml").read_text()
    assert "sundar-kaand" in content


def test_custom_num_verses(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "test-collection", num_verses=5)
    for i in range(1, 6):
        assert (tmp_path / "_verses" / "test-collection" / f"verse-{i:02d}.md").exists()
    assert not (tmp_path / "_verses" / "test-collection" / "verse-06.md").exists()


def test_collection_next_steps_mentions_canonical_first_optional_theme_and_flow(tmp_path, capsys):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "shiv-puran", num_verses=3)

    out = capsys.readouterr().out
    assert "1. Add canonical source text (plain text), either:" in out
    assert "data/sources/shiv-puran/..." in out
    assert "data/sources/shiv-puran.txt" in out
    assert "verse-parse-source --collection shiv-puran" in out
    assert "Output: data/verses/shiv-puran.yaml" in out
    assert "3. Configure environment before generation:" in out
    assert "cp .env.example .env" in out
    assert "Set OPENAI_API_KEY (and ELEVENLABS_API_KEY if generating audio)" in out
    assert "Optional: customize theme in data/themes/shiv-puran/modern-minimalist.yml" in out
    assert "verse-generate --collection shiv-puran --verse 1 --regenerate-content" in out
    assert "bundle install" in out
    assert "bundle exec jekyll serve" in out
    assert out.index("bundle install") < out.index("bundle exec jekyll serve")
    assert "verse-generate --collection shiv-puran --all" in out
    assert "verse-generate --collection shiv-puran --verse 1-3" in out
    assert "verse-generate --collection shiv-puran --next" in out


def test_project_next_steps_with_collections_do_not_duplicate_generic_flow(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    init_project(project_name=None, collections=["shiv-puran"], num_verses=3)

    out = capsys.readouterr().out
    assert "2. Follow the collection-specific next steps shown above." in out
    assert "verse-parse-source --collection <collection-key>" not in out
    assert "verse-generate --collection <collection-key> --all" not in out

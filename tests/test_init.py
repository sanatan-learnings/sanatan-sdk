"""Tests for verse_sdk/cli/init.py — project scaffolding."""

from pathlib import Path

from verse_sdk.cli.init import (
    create_directory_structure,
    create_example_collection,
    create_template_files,
    init_project,
)
from verse_sdk.cli.init import (
    main as init_main,
)

# ---------------------------------------------------------------------------
# create_directory_structure
# ---------------------------------------------------------------------------

def test_creates_required_dirs(tmp_path):
    create_directory_structure(tmp_path)
    for d in ["_data", "_layouts", "_verses", "data/themes", "data/verses", "data/scenes"]:
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
        "_layouts/default.html",
        "_layouts/home.html",
        "_layouts/collection.html",
        "_layouts/verse.html",
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
    assert 'gem "minima"' not in content


def test_config_does_not_reference_minima(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "my-project")
    content = (tmp_path / "_config.yml").read_text()
    assert "theme: minima" not in content
    assert "collections:" in content
    assert "verses:" in content
    assert "output: true" in content


def test_index_page_has_jekyll_frontmatter(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "my-project")
    content = (tmp_path / "index.md").read_text()
    assert content.startswith("---\n")
    assert "layout: home" in content
    assert "site.data.collections" in content
    assert "item[1].enabled" not in content
    assert "cfg.enabled" in content


# ---------------------------------------------------------------------------
# create_example_collection
# ---------------------------------------------------------------------------

def test_does_not_create_sample_verse_markdown_files(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "hanuman-chalisa", num_verses=3)
    for i in range(1, 4):
        f = tmp_path / "_verses" / "hanuman-chalisa" / f"verse-{i:02d}.md"
        assert not f.exists(), f"Unexpected sample verse markdown: {f.name}"


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
    content = scenes.read_text()
    assert "title-page:" in content
    assert "title: Hanuman Chalisa Title Page" in content
    assert "Close-up portrait of the primary deity/subject" in content
    assert "card-page:" in content
    assert "title: Hanuman Chalisa Card Image" in content
    assert "verse-01:" not in content


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
    assert 'hi: "सुंदर काण्ड"' in content


def test_collection_entry_inserted_before_example_block(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "shiv-puran", num_verses=3)

    content = (tmp_path / "_data" / "collections.yml").read_text()
    assert "shiv-puran:" in content
    assert "# Example:" in content
    assert content.index("shiv-puran:") < content.index("# Example:")
    assert 'hi: "शिव पुराण"' in content


def test_creates_collection_index_page_for_local_preview(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "shiv-puran", num_verses=3)

    collection_index = tmp_path / "shiv-puran" / "index.md"
    assert collection_index.exists()
    content = collection_index.read_text()
    assert "layout: collection" in content
    assert "collection_key: shiv-puran" in content


def test_creates_collection_title_image_placeholder(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "shiv-puran", num_verses=3)

    card_image = tmp_path / "images" / "shiv-puran" / "card.png"
    assert card_image.exists()
    assert card_image.stat().st_size > 0

    title_image = tmp_path / "images" / "shiv-puran" / "title.png"
    assert title_image.exists()
    assert title_image.stat().st_size > 0


def test_collection_layout_references_title_image(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")

    index_content = (tmp_path / "index.md").read_text()
    assert "/images/{{ key }}/modern-minimalist/card-page.png" in index_content
    assert "this.src='/images/{{ key }}/card.png'" in index_content

    layout = (tmp_path / "_layouts" / "collection.html").read_text()
    assert "/images/{{ collection_key }}/modern-minimalist/title-page.png" in layout
    assert "this.src='/images/{{ collection_key }}/title.png'" in layout
    assert "verse.collection_key == collection_key" in layout
    assert "v.path contains" not in layout


def test_custom_num_verses(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "test-collection", num_verses=5)
    content = (tmp_path / "data" / "verses" / "test-collection.yaml").read_text()
    assert "    - verse-05" in content
    assert "    - verse-06" not in content


def test_project_next_steps_with_collection_are_consolidated_and_concrete(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    init_project(project_name=None, collections=["shiv-puran"], num_verses=3)

    out = capsys.readouterr().out
    assert "✅ Project initialized successfully!" in out
    assert "📝 Next steps:" in out
    assert "2. Add canonical source text (plain text), either:" in out
    assert "data/sources/shiv-puran/..." in out
    assert "data/sources/shiv-puran.txt" in out
    assert "verse-parse-source --collection shiv-puran" in out
    assert "Output: data/verses/shiv-puran.yaml" in out
    assert "1. Configure environment before generation:" in out
    assert "cp .env.example .env" in out
    assert "Set OPENAI_API_KEY (and ELEVENLABS_API_KEY if generating audio)" in out
    assert "Optional: customize theme in data/themes/shiv-puran/modern-minimalist.yml" in out
    assert "verse-generate --collection shiv-puran --verse 1" in out
    assert "verse-generate --collection shiv-puran --verse 1 --regenerate-content" not in out
    assert "verse-images --collection shiv-puran --theme modern-minimalist --verse title-page" in out
    assert "verse-images --collection shiv-puran --theme modern-minimalist --verse card-page" in out
    assert "Outputs: images/shiv-puran/modern-minimalist/title-page.png and card-page.png" in out
    assert "bundle install" in out
    assert "bundle exec jekyll serve" in out
    assert out.index("bundle install") < out.index("bundle exec jekyll serve")
    assert "9. Optional next: generate full collection:" in out
    assert "verse-generate --collection shiv-puran --all" in out
    assert "verse-generate --collection shiv-puran --verse 1-3" in out
    assert "verse-generate --collection shiv-puran --next" in out
    assert "10. Optional quality check: verse-validate" in out
    assert "11. Optional advanced workflows: verse-embeddings / verse-index-sources / verse-puranic-context / verse-deploy" in out
    assert "12. Docs for advanced workflows: https://github.com/sanatan-learnings/sanatan-verse-sdk/blob/main/docs/usage.md" in out
    assert "Follow the collection-specific next steps shown above" not in out


def test_collection_next_steps_mentions_canonical_first_optional_theme_and_flow(tmp_path, capsys):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "shiv-puran", num_verses=3)

    out = capsys.readouterr().out
    assert "Collection 'shiv-puran' initialized (canonical placeholders: 3)" in out
    assert "📝 Next steps:" not in out


def test_project_next_steps_with_collections_do_not_duplicate_generic_flow(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    init_project(project_name=None, collections=["shiv-puran"], num_verses=3)

    out = capsys.readouterr().out
    assert "2. Follow the collection-specific next steps shown above." not in out
    assert "verse-parse-source --collection <collection-key>" not in out
    assert "verse-generate --collection <collection-key> --all" not in out


def test_issue_73_no_duplicate_next_steps_sections(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    init_project(project_name=None, collections=["shiv-puran"], num_verses=3)

    out = capsys.readouterr().out
    assert out.count("📝 Next steps:") == 1
    assert "✅ Collection 'shiv-puran' initialized (canonical placeholders: 3)\n   Next steps:" not in out
    assert "1. Copy .env.example to .env and add your API keys" not in out
    assert "2. Follow the collection-specific next steps shown above." not in out


def test_issue_74_cli_output_uses_default_first_generation_command(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["verse-init", "--collection", "shiv-puran"])

    init_main()

    out = capsys.readouterr().out
    assert "verse-generate --collection shiv-puran --verse 1" in out
    assert "verse-generate --collection shiv-puran --verse 1 --regenerate-content" not in out

"""Tests for verse_sdk/cli/init.py — project scaffolding."""

import subprocess
from pathlib import Path

from verse_sdk.cli.init import (
    create_directory_structure,
    create_example_collection,
    create_template_files,
    init_project,
    normalize_repo_url,
    resolve_collection_theme,
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
        "_data/translations/en.yml",
        "_data/translations/hi.yml",
        ".gitignore",
        "Gemfile",
        "_config.yml",
        "_layouts/default.html",
        "_layouts/home.html",
        "_layouts/collection.html",
        "_layouts/verse.html",
        "assets/css/style.css",
        "assets/css/print.css",
        "assets/js/navigation.js",
        "assets/js/language.js",
        "assets/js/theme.js",
        "assets/js/guidance.js",
        "index.html",
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
    assert 'gem "jekyll-seo-tag"' in content
    assert 'gem "minima"' not in content


def test_config_does_not_reference_minima(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "my-project")
    content = (tmp_path / "_config.yml").read_text()
    assert "theme: minima" not in content
    assert "collections:" in content
    assert "verses:" in content
    assert "output: true" in content
    assert "plugins:" in content
    assert "jekyll-seo-tag" in content
    assert "banner_title:" in content
    assert "banner_subtitle:" in content
    assert "search_verses_url:" in content


def test_config_prefills_project_repository_url_from_git_origin(tmp_path, monkeypatch):
    create_directory_structure(tmp_path)

    def _fake_run(cmd, cwd, check, capture_output, text):
        assert cmd == ["git", "config", "--get", "remote.origin.url"]
        assert cwd == tmp_path
        return subprocess.CompletedProcess(cmd, 0, stdout="git@github.com:acme/shiv-puran.git\n")

    monkeypatch.setattr("subprocess.run", _fake_run)
    create_template_files(tmp_path, "my-project")
    content = (tmp_path / "_config.yml").read_text()
    assert 'project_repository_url: "https://github.com/acme/shiv-puran"' in content


def test_config_uses_placeholder_project_repository_url_when_no_remote(tmp_path, monkeypatch):
    create_directory_structure(tmp_path)

    def _fake_run(cmd, cwd, check, capture_output, text):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr("subprocess.run", _fake_run)
    create_template_files(tmp_path, "my-project")
    content = (tmp_path / "_config.yml").read_text()
    assert 'project_repository_url: "https://github.com/<your-org>/<your-repo>"' in content


def test_normalize_repo_url_handles_https_and_ssh():
    assert normalize_repo_url("git@github.com:org/repo.git") == "https://github.com/org/repo"
    assert normalize_repo_url("https://github.com/org/repo.git") == "https://github.com/org/repo"
    assert normalize_repo_url("https://github.com/org/repo") == "https://github.com/org/repo"


def test_index_page_has_jekyll_frontmatter(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "my-project")
    content = (tmp_path / "index.html").read_text()
    assert content.startswith("---\n")
    assert "layout: home" in content
    assert "site.data.collections" in content
    assert "cfg.enabled" in content
    assert "class=\"collections-grid card-grid\"" in content
    assert "home-hero-media" in content
    assert "Ask Shiva" in content
    assert "Search Verses" in content
    assert "site.search_verses_url" in content
    assert "Sacred Text" in content
    assert "End-to-End Workflow" not in content
    assert "Enabled collections" not in content


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
    assert "cover:" in content
    assert "title: Hanuman Chalisa Cover" in content
    assert "Primary subject: Lord Hanuman" in content
    assert "gada (mace)" in content
    assert "verse-01:" not in content


def test_creates_site_scenes_file(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    site_scenes = tmp_path / "data" / "scenes" / "site.yml"
    assert site_scenes.exists()
    content = site_scenes.read_text()
    assert "scenes:" in content
    assert "cover:" in content


def test_scenes_file_is_collection_aware_for_shiva(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "shiv-puran", num_verses=2)
    scenes = tmp_path / "data" / "scenes" / "shiv-puran.yml"
    content = scenes.read_text()
    assert "Primary subject: Lord Shiva" in content
    assert "Kailash-inspired" in content


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
    assert "sundar-kaand:\n" in content
    sundar_block = content.split("sundar-kaand:\n", 1)[1]
    next_top_level = sundar_block.find("\n# Example:")
    if next_top_level != -1:
        sundar_block = sundar_block[:next_top_level]
    assert "total_verses:" not in sundar_block


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

    collection_index = tmp_path / "shiv-puran" / "index.html"
    assert collection_index.exists()
    content = collection_index.read_text()
    assert "layout: collection" in content
    assert "collection_key: shiv-puran" in content


def test_does_not_create_invalid_theme_scoped_collection_image_placeholders(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    create_example_collection(tmp_path, "shiv-puran", num_verses=3)

    theme_cover = tmp_path / "images" / "shiv-puran" / "modern-minimalist" / "cover.png"
    assert not theme_cover.exists()

    card_image = tmp_path / "images" / "shiv-puran" / "card.png"
    assert not card_image.exists()

    title_image = tmp_path / "images" / "shiv-puran" / "title.png"
    assert not title_image.exists()


def test_prefers_verse_images_generation_when_api_key_present(tmp_path, monkeypatch):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("shutil.which", lambda cmd: "verse-images" if cmd == "verse-images" else None)

    calls = []

    def _fake_run(cmd, cwd, check, capture_output, text):
        calls.append(cmd)
        verse_id = cmd[cmd.index("--verse") + 1]
        out = tmp_path / "images" / "shiv-puran" / "modern-minimalist" / f"{verse_id}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")
        return None

    monkeypatch.setattr("subprocess.run", _fake_run)

    create_example_collection(tmp_path, "shiv-puran", num_verses=2)

    assert len(calls) == 1
    assert any("--verse" in cmd and "cover" in cmd for cmd in calls)
    assert (tmp_path / "images" / "shiv-puran" / "modern-minimalist" / "cover.png").exists()
    assert (tmp_path / "images" / "cover.png").exists()


def test_reports_images_pending_when_api_key_missing(tmp_path, monkeypatch, capsys):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    create_example_collection(tmp_path, "shiv-puran", num_verses=2)

    out = capsys.readouterr().out
    assert "Images pending for shiv-puran (no OPENAI_API_KEY)" in out
    assert "verse-images --collection shiv-puran --theme modern-minimalist --verse cover" in out


def test_collection_layout_references_title_image(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")

    index_content = (tmp_path / "index.html").read_text()
    assert "{% assign theme_name = cfg.image_theme | default: cfg.theme | default: cfg.default_theme" in index_content
    assert "{% assign generated_count = 0 %}" in index_content
    assert "/images/{{ key }}/{{ theme_name }}/cover.png" in index_content
    assert "{{ generated_count }} of {{ cfg.total_verses }}" in index_content
    assert "{{ generated_count }} of ?" in index_content
    assert "this.src='/images/{{ key }}/card.png'" not in index_content
    assert "class=\"collection-card card\"" in index_content

    layout = (tmp_path / "_layouts" / "collection.html").read_text()
    assert "{% assign theme_name = collection_cfg.image_theme | default: collection_cfg.theme | default: collection_cfg.default_theme" in layout
    assert "/images/{{ collection_key }}/{{ theme_name }}/cover.png" in layout
    assert "this.src='/images/{{ collection_key }}/title.png'" not in layout
    assert "verse.collection_key == collection_key" in layout
    assert "<span data-lang=\"en\">{{ collection_name_en }}</span>" in layout
    assert "<span data-lang=\"hi\">{{ collection_name_hi | default: collection_name_en }}</span>" in layout
    assert "Back to Home" not in layout
    assert "Workflow Guide" not in layout
    assert "class=\"card verse-card\"" in layout
    assert "collection-hero card" in layout
    assert "collection-hero-media" in layout
    assert "Start Reading" in layout
    assert "site.static_files" in layout
    assert "{{ verse.verse_id | default: verse.title | default: verse.basename }}" not in layout
    assert "v.path contains" not in layout


def test_index_layout_orders_hero_then_sacred_text(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    content = (tmp_path / "index.html").read_text()
    assert content.index("home-hero") < content.index("Sacred Text")
    assert "/images/cover.png" in content


def test_resolve_collection_theme_uses_project_default(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")

    verse_cfg = tmp_path / "_data" / "verse-config.yml"
    verse_cfg.write_text("defaults:\n  image_theme: traditional\n", encoding="utf-8")

    assert resolve_collection_theme(tmp_path, "shiv-puran") == "traditional"


def test_resolve_collection_theme_prefers_collection_override(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")

    verse_cfg = tmp_path / "_data" / "verse-config.yml"
    verse_cfg.write_text("defaults:\n  image_theme: traditional\n", encoding="utf-8")

    collections = tmp_path / "_data" / "collections.yml"
    collections.write_text(
        "shiv-puran:\n"
        "  enabled: true\n"
        "  name:\n"
        "    en: Shiv Puran\n"
        "  image_theme: temple-art\n",
        encoding="utf-8",
    )

    assert resolve_collection_theme(tmp_path, "shiv-puran") == "temple-art"


def test_default_layout_uses_assets_and_configurable_header(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    layout = (tmp_path / "_layouts" / "default.html").read_text()
    assert "/assets/css/style.css" in layout
    assert "/assets/css/print.css" in layout
    assert "/assets/js/navigation.js" in layout
    assert "/assets/js/language.js" in layout
    assert "/assets/js/theme.js" in layout
    assert "/assets/js/guidance.js" in layout
    assert "{% seo %}" in layout
    assert "site.banner_title | default: site.title" in layout
    assert "site.banner_subtitle | default: site.description" in layout
    assert "active_collection_cfg.banner_theme" in layout
    assert "banner-theme-{{ banner_theme | slugify }}" in layout
    assert "subject_hint_lc contains 'shiv'" in layout
    assert "footer-links" in layout
    assert "May divine wisdom guide your study and practice." in layout
    assert "site.project_repository_url" in layout
    assert "site.usage_guide_url" in layout
    assert "site.ask_shiva_url" in layout
    assert "site.shiva_quiz_url" in layout
    assert "site.contribute_url" in layout
    assert "Ask Shiva" in layout
    assert "Shiva Quiz" in layout
    assert "Contribute" in layout
    assert "sanatan-learnings/sanatan-verse-sdk" not in layout

    css = (tmp_path / "assets" / "css" / "style.css").read_text()
    assert "body.banner-theme-shiva" in css
    assert ".site-footer" in css

    config = (tmp_path / "_config.yml").read_text()
    assert "project_repository_url:" in config
    assert "usage_guide_url:" in config
    assert "ask_shiva_url:" in config
    assert "shiva_quiz_url:" in config
    assert "contribute_url:" in config


def test_home_layout_does_not_duplicate_title_and_description(tmp_path):
    create_directory_structure(tmp_path)
    create_template_files(tmp_path, "test")
    layout = (tmp_path / "_layouts" / "home.html").read_text()
    assert "{{ page.title | default: site.title }}" not in layout
    assert "{{ site.description }}" not in layout


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
    assert "Optional: validate or re-generate collection title/card images:" not in out
    assert "verse-images --verse title-page" not in out
    assert "verse-images --verse card-page" not in out
    assert "Collection cover image is auto-generated in this first-verse flow when OPENAI_API_KEY is available." in out
    assert "images/cover.png and images/<collection>/<theme>/cover.png" in out
    assert "bundle install" in out
    assert "bundle exec jekyll serve" in out
    assert out.index("bundle install") < out.index("bundle exec jekyll serve")
    assert "✅ Core flow complete (steps 1-7)." in out
    assert "Optional next steps:" in out
    assert out.index("bundle exec jekyll serve") < out.index("✅ Core flow complete (steps 1-7).")
    assert out.index("✅ Core flow complete (steps 1-7).") < out.index("8. Optional next: generate full collection:")
    assert "8. Optional next: generate full collection:" in out
    assert "verse-generate --collection shiv-puran --all" in out
    assert "verse-generate --collection shiv-puran --verse 1-3" in out
    assert "verse-generate --collection shiv-puran --next" in out
    assert "9. Optional quality check: verse-validate" in out
    assert "10. Optional advanced workflows: verse-embeddings / verse-index-sources / verse-puranic-context / verse-deploy" in out
    assert "11. Docs for advanced workflows: https://github.com/sanatan-learnings/sanatan-verse-sdk/blob/main/docs/usage.md" in out
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

"""Tests for image validation and atomic writes in generate_theme_images."""

import io
from types import SimpleNamespace

from PIL import Image

from verse_sdk.images.generate_theme_images import (
    ImageGenerator,
    _is_valid_image_file,
    _validate_image_bytes,
    _write_image_atomic,
    resolve_collection_arg,
    resolve_theme_arg,
)


def _valid_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(255, 200, 120)).save(buf, format="PNG")
    return buf.getvalue()


def test_validate_image_bytes_rejects_empty():
    try:
        _validate_image_bytes(b"")
        assert False, "Expected ValueError for empty payload"
    except ValueError as exc:
        assert "empty" in str(exc).lower()


def test_write_image_atomic_writes_valid_file(tmp_path):
    output = tmp_path / "title-page.png"
    _write_image_atomic(output, _valid_png_bytes())
    assert output.exists()
    assert output.stat().st_size > 0
    assert _is_valid_image_file(output) is True


def test_write_image_atomic_does_not_leave_partial_file_on_invalid_bytes(tmp_path):
    output = tmp_path / "card-page.png"
    try:
        _write_image_atomic(output, b"not-a-real-image")
        assert False, "Expected ValueError for invalid image payload"
    except ValueError:
        pass
    assert not output.exists()
    assert not (tmp_path / "card-page.png.tmp").exists()


def test_generate_image_regenerates_when_existing_file_is_invalid(tmp_path, monkeypatch):
    output_dir = tmp_path / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    broken = output_dir / "title-page.png"
    broken.write_bytes(b"")

    # Build a generator without invoking networked constructor behavior.
    gen = ImageGenerator.__new__(ImageGenerator)
    gen.output_dir = output_dir
    gen.theme = "modern-minimalist"
    gen.style_modifier = ""
    gen.build_full_prompt = lambda prompt: prompt
    gen.client = SimpleNamespace(
        images=SimpleNamespace(
            generate=lambda **kwargs: SimpleNamespace(data=[SimpleNamespace(url="https://example.com/image.png")])
        )
    )

    class DummyResp:
        content = _valid_png_bytes()

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr("verse_sdk.images.generate_theme_images.requests.get", lambda *args, **kwargs: DummyResp())
    monkeypatch.setattr("verse_sdk.images.generate_theme_images.time.sleep", lambda *_args, **_kwargs: None)

    ok = gen.generate_image("title-page.png", "scene prompt", retry_count=1)
    assert ok is True
    assert broken.exists()
    assert broken.stat().st_size > 0
    assert _is_valid_image_file(broken) is True


def test_resolve_collection_arg_auto_selects_single_configured_collection(tmp_path):
    data_dir = tmp_path / "_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "collections.yml").write_text(
        "shiv-puran:\n"
        "  enabled: true\n"
        "  name:\n"
        "    en: Shiv Puran\n",
        encoding="utf-8",
    )

    assert resolve_collection_arg(None, project_dir=tmp_path) == "shiv-puran"


def test_resolve_collection_arg_errors_when_multiple_configured_collections(tmp_path):
    data_dir = tmp_path / "_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "collections.yml").write_text(
        "shiv-puran:\n"
        "  enabled: true\n"
        "ramayan:\n"
        "  enabled: true\n",
        encoding="utf-8",
    )

    try:
        resolve_collection_arg(None, project_dir=tmp_path)
        assert False, "Expected ValueError for ambiguous collection"
    except ValueError as exc:
        assert "Multiple collections found" in str(exc)
        assert "ramayan" in str(exc)
        assert "shiv-puran" in str(exc)


def test_resolve_theme_arg_prefers_configured_default_theme(tmp_path):
    data_dir = tmp_path / "_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "collections.yml").write_text(
        "shiv-puran:\n"
        "  enabled: true\n"
        "  image_theme: temple-art\n",
        encoding="utf-8",
    )
    themes_dir = tmp_path / "data" / "themes" / "shiv-puran"
    themes_dir.mkdir(parents=True, exist_ok=True)
    (themes_dir / "temple-art.yml").write_text("theme: {}\n", encoding="utf-8")
    (themes_dir / "modern-minimalist.yml").write_text("theme: {}\n", encoding="utf-8")

    assert resolve_theme_arg("shiv-puran", None, project_dir=tmp_path) == "temple-art"


def test_resolve_theme_arg_auto_selects_single_theme_file(tmp_path):
    themes_dir = tmp_path / "data" / "themes" / "shiv-puran"
    themes_dir.mkdir(parents=True, exist_ok=True)
    (themes_dir / "modern-minimalist.yml").write_text("theme: {}\n", encoding="utf-8")

    assert resolve_theme_arg("shiv-puran", None, project_dir=tmp_path) == "modern-minimalist"


def test_resolve_theme_arg_errors_when_multiple_themes_without_default(tmp_path):
    themes_dir = tmp_path / "data" / "themes" / "shiv-puran"
    themes_dir.mkdir(parents=True, exist_ok=True)
    (themes_dir / "modern-minimalist.yml").write_text("theme: {}\n", encoding="utf-8")
    (themes_dir / "kids-friendly.yml").write_text("theme: {}\n", encoding="utf-8")

    try:
        resolve_theme_arg("shiv-puran", None, project_dir=tmp_path)
        assert False, "Expected ValueError for ambiguous themes"
    except ValueError as exc:
        assert "Multiple themes found" in str(exc)
        assert "kids-friendly" in str(exc)
        assert "modern-minimalist" in str(exc)

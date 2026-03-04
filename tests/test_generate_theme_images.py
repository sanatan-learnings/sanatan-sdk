"""Tests for image validation and atomic writes in generate_theme_images."""

import io
from types import SimpleNamespace

from PIL import Image

from verse_sdk.images.generate_theme_images import (
    ImageGenerator,
    _is_valid_image_file,
    _validate_image_bytes,
    _write_image_atomic,
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

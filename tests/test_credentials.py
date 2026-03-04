"""Tests for shared credential resolution utilities."""

from verse_sdk.utils.credentials import resolve_api_key


def test_resolve_api_key_prefers_explicit_over_env_and_dotenv(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=dotenv-key\n", encoding="utf-8")

    resolved = resolve_api_key("OPENAI_API_KEY", explicit_key="cli-key", project_dir=tmp_path)
    assert resolved == "cli-key"


def test_resolve_api_key_prefers_env_over_dotenv(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=dotenv-key\n", encoding="utf-8")

    resolved = resolve_api_key("OPENAI_API_KEY", explicit_key=None, project_dir=tmp_path)
    assert resolved == "env-key"


def test_resolve_api_key_falls_back_to_dotenv(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=dotenv-key\n", encoding="utf-8")

    resolved = resolve_api_key("OPENAI_API_KEY", explicit_key=None, project_dir=tmp_path)
    assert resolved == "dotenv-key"


def test_resolve_api_key_filters_placeholder_values(tmp_path, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "your-api-key-here")
    (tmp_path / ".env").write_text("ELEVENLABS_API_KEY=real-dotenv-key\n", encoding="utf-8")

    resolved = resolve_api_key(
        "ELEVENLABS_API_KEY",
        explicit_key=None,
        project_dir=tmp_path,
        placeholder_values={"your-api-key-here"},
    )
    assert resolved == "real-dotenv-key"

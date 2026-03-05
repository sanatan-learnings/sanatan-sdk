"""Tests for verse-generate verbosity controls around nested subcommands."""

import subprocess

import pytest

from verse_sdk.cli.generate import run_subcommand


def test_run_subcommand_default_suppresses_nested_output(monkeypatch):
    seen = {}

    def _fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0, stdout="noisy output", stderr="")

    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = run_subcommand(["verse-images", "--help"], step_name="image generation", verbose=False, quiet=False)

    assert result.returncode == 0
    assert seen["kwargs"].get("capture_output") is True
    assert seen["kwargs"].get("text") is True


def test_run_subcommand_verbose_passes_through_output(monkeypatch):
    seen = {}

    def _fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", _fake_run)

    run_subcommand(["verse-audio", "--help"], step_name="audio generation", verbose=True, quiet=False)

    assert "capture_output" not in seen["kwargs"]
    assert "stdout" not in seen["kwargs"]
    assert seen["kwargs"].get("text") is True


def test_run_subcommand_failure_shows_compact_hint(monkeypatch, capsys):
    def _fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(
            2,
            cmd,
            output="line1\nline2",
            stderr="e1\ne2\ne3",
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(subprocess.CalledProcessError):
        run_subcommand(["verse-embeddings"], step_name="embeddings update", verbose=False, quiet=False)

    err = capsys.readouterr().err
    assert "embeddings update failed" in err
    assert "Re-run with --verbose" in err

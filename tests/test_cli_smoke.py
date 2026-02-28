"""Smoke tests — verify CLI entry points load and respond to --help."""

import subprocess
import sys

COMMANDS = [
    "verse-generate",
    "verse-embeddings",
    "verse-audio",
    "verse-images",
    "verse-status",
    "verse-sync",
    "verse-translate",
    "verse-init",
    "verse-validate",
    "verse-add",
    "verse-puranic-context",
    "verse-index-sources",
    "verse-help",
]


def _run(cmd, *args):
    return subprocess.run(
        [sys.executable, "-m", "verse_sdk.cli." + cmd.replace("verse-", "").replace("-", "_"), *args],
        capture_output=True,
        text=True,
    )


def _run_entry(cmd, *args):
    """Run via the installed entry point script name."""
    return subprocess.run(
        [cmd, *args],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Module import smoke tests (no API calls, no file system)
# ---------------------------------------------------------------------------

def test_import_puranic_context():
    import verse_sdk.cli.puranic_context  # noqa: F401


def test_import_index_sources():
    import verse_sdk.cli.index_sources  # noqa: F401


def test_import_validate():
    import verse_sdk.cli.validate  # noqa: F401


def test_import_init():
    import verse_sdk.cli.init  # noqa: F401


def test_import_help():
    import verse_sdk.cli.help  # noqa: F401


def test_import_generate():
    import verse_sdk.cli.generate  # noqa: F401


def test_import_status():
    import verse_sdk.cli.status  # noqa: F401


def test_import_sync():
    import verse_sdk.cli.sync  # noqa: F401


def test_import_translate():
    import verse_sdk.cli.translate  # noqa: F401


def test_import_add():
    import verse_sdk.cli.add  # noqa: F401


def test_import_generate_embeddings():
    import verse_sdk.embeddings.generate_embeddings  # noqa: F401


def test_import_local_embeddings():
    import verse_sdk.embeddings.local_embeddings  # noqa: F401


def test_import_file_utils():
    import verse_sdk.utils.file_utils  # noqa: F401


def test_import_yaml_parser():
    import verse_sdk.utils.yaml_parser  # noqa: F401


# ---------------------------------------------------------------------------
# --help exits 0 (argparse commands)
# ---------------------------------------------------------------------------

def _help_exits_zero(module_path):
    result = subprocess.run(
        [sys.executable, "-c", f"import sys; sys.argv=['cmd','--help']; from {module_path} import main; main()"],
        capture_output=True,
        text=True,
    )
    # argparse --help exits with code 0
    assert result.returncode == 0, f"{module_path} --help failed:\n{result.stderr}"
    assert "usage" in result.stdout.lower() or "Usage" in result.stdout


def test_help_verse_init():
    _help_exits_zero("verse_sdk.cli.init")


def test_help_verse_validate():
    _help_exits_zero("verse_sdk.cli.validate")


def test_help_verse_add():
    _help_exits_zero("verse_sdk.cli.add")


def test_help_verse_status():
    _help_exits_zero("verse_sdk.cli.status")


def test_help_verse_sync():
    _help_exits_zero("verse_sdk.cli.sync")


def test_help_verse_translate():
    _help_exits_zero("verse_sdk.cli.translate")


def test_help_verse_puranic_context():
    _help_exits_zero("verse_sdk.cli.puranic_context")


def test_help_verse_index_sources():
    _help_exits_zero("verse_sdk.cli.index_sources")


def test_help_verse_generate():
    _help_exits_zero("verse_sdk.cli.generate")


def test_help_verse_deploy():
    result = subprocess.run(
        [sys.executable, "-c", "import sys; sys.argv=['verse-deploy','--help']; from verse_sdk.deployment.deploy import main; main()"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"verse-deploy --help failed:\n{result.stderr}"
    assert "usage" in result.stdout.lower()


# ---------------------------------------------------------------------------
# verse-init functional smoke test
# ---------------------------------------------------------------------------

def test_verse_init_creates_structure(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.argv=['verse-init','--project-name','testproj']; "
         f"import os; os.chdir('{tmp_path}'); "
         f"from verse_sdk.cli.init import main; main()"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    project = tmp_path / "testproj"
    assert project.is_dir()
    assert (project / "_data" / "collections.yml").exists()
    assert (project / "_data" / "verse-config.yml").exists()
    assert (project / ".env.example").exists()


def test_verse_init_with_collection(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.argv=['verse-init','--project-name','myproj','--collection','hanuman-chalisa']; "
         f"import os; os.chdir('{tmp_path}'); "
         f"from verse_sdk.cli.init import main; main()"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "myproj" / "_verses" / "hanuman-chalisa").is_dir()
    assert (tmp_path / "myproj" / "data" / "verses" / "hanuman-chalisa.yaml").exists()

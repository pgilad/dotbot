import os
import stat
from collections.abc import Callable

import pytest

from tests.conftest import Dotfiles


@pytest.mark.parametrize("directory", ["~/a", "~/b/c"])
def test_directory_creation(
    home: str, directory: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Test creating directories, including nested directories."""

    _ = home
    dotfiles.write_config([{"create": [directory]}])
    run_dotbot()

    expanded_directory = os.path.abspath(os.path.expanduser(directory))
    assert os.path.isdir(expanded_directory)
    assert os.stat(expanded_directory).st_mode & 0o777 == 0o777


def test_default_mode(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Test creating a directory with an explicit default mode.

    Note: `os.chmod()` on Windows only supports changing write permissions.
    Therefore, this test is restricted to testing read-only access.
    """

    _ = home
    read_only = 0o777 - stat.S_IWUSR - stat.S_IWGRP - stat.S_IWOTH
    config = [{"defaults": {"create": {"mode": read_only}}}, {"create": ["~/a"]}]
    dotfiles.write_config(config)
    run_dotbot()

    directory = os.path.abspath(os.path.expanduser("~/a"))
    assert os.stat(directory).st_mode & stat.S_IWUSR == 0
    assert os.stat(directory).st_mode & stat.S_IWGRP == 0
    assert os.stat(directory).st_mode & stat.S_IWOTH == 0


def test_default_mode_override(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Test creating a directory that overrides an explicit default mode.

    Note: `os.chmod()` on Windows only supports changing write permissions.
    Therefore, this test is restricted to testing read-only access.
    """

    _ = home
    read_only = 0o777 - stat.S_IWUSR - stat.S_IWGRP - stat.S_IWOTH
    config = [
        {"defaults": {"create": {"mode": read_only}}},
        {"create": {"~/a": {"mode": 0o777}}},
    ]
    dotfiles.write_config(config)
    run_dotbot()

    directory = os.path.abspath(os.path.expanduser("~/a"))
    assert os.stat(directory).st_mode & stat.S_IWUSR == stat.S_IWUSR
    assert os.stat(directory).st_mode & stat.S_IWGRP == stat.S_IWGRP
    assert os.stat(directory).st_mode & stat.S_IWOTH == stat.S_IWOTH


def test_create_dry_run(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the create plugin does not create directories during a dry run."""

    os.makedirs(os.path.join(home, "existing"))
    dotfiles.write_config([{"create": ["~/a", "~/existing"]}])
    run_dotbot("-n", "-v")

    directory = os.path.abspath(os.path.expanduser("~/a"))
    assert not os.path.exists(directory)

    lines = capfd.readouterr().out.splitlines()
    assert any(
        line.strip() == f"Would create directory {os.path.join('~', 'a')}"
        for line in lines
    )
    assert any(
        f"Directory exists {os.path.join('~', 'existing')}" == line.strip()
        for line in lines
    )
    assert "create: 1 to create, 1 in place" in lines


def test_create_summary(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the summary line counts the directories of each create."""

    os.makedirs(os.path.join(home, "existing"))
    dotfiles.write_config([{"create": ["~/a", "~/existing"]}, {"create": []}])
    run_dotbot()

    lines = capfd.readouterr().out.splitlines()
    assert lines[-3:-1] == ["create: 1 created, 1 in place", "create: nothing to do"]


def test_create_undefined_variable_warns(
    capfd: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify create warns about undefined environment variables.

    The path is still created with the name as written.
    """

    monkeypatch.delenv("PEAR", raising=False)
    dotfiles.write_config([{"create": ["~/$PEAR"]}])
    run_dotbot()

    assert os.path.isdir(os.path.join(home, "$PEAR"))
    assert "Undefined environment variable $PEAR in ~/$PEAR" in capfd.readouterr().err


def test_create_file_in_the_way(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a file where a directory should be gives a warning.

    The file is kept, and the run doesn't fail, as before.
    """

    with open(os.path.join(home, "a"), "w") as file:
        file.write("apple")
    dotfiles.write_config([{"create": ["~/a"]}])
    run_dotbot()

    assert os.path.isfile(os.path.join(home, "a"))
    output = capfd.readouterr()
    assert (
        f"warning: {os.path.join('~', 'a')} already exists but is not a directory"
        in output.err.splitlines()
    )
    assert "create: 1 not a directory" in output.out.splitlines()

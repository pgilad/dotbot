import os
import sys

import pytest

from dotbot.util.common import display_path


def set_home(monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    monkeypatch.setenv("USERPROFILE" if sys.platform == "win32" else "HOME", path)


def test_display_path_home(home: str) -> None:
    """Verify that the home directory and the paths in it start with ~."""

    assert display_path(home) == "~"
    assert display_path(os.path.join(home, ".config", "app")) == os.path.join(
        "~", ".config", "app"
    )


def test_display_path_outside_of_home(root: str, home: str) -> None:
    """Verify that the paths outside of the home directory don't change.

    A path that starts with the name of the home directory (such as
    /home/user2 for /home/user) is outside of it, and so is a relative path.
    """

    for path in (
        root,
        home + "2",
        os.path.join(home + "2", "file"),
        os.path.join("relative", "file"),
    ):
        assert display_path(path) == path


def test_display_path_symlinked_home(
    monkeypatch: pytest.MonkeyPatch, root: str
) -> None:
    """Verify that the paths in a symlinked home directory start with ~.

    Dotbot shows canonical target paths, which don't have the symlink.
    """

    real_home = os.path.join(root, "real-home")
    os.makedirs(real_home)
    home = os.path.join(root, "home")
    os.symlink(real_home, home, target_is_directory=True)
    set_home(monkeypatch, home)

    for directory in (home, os.path.realpath(real_home)):
        assert display_path(os.path.join(directory, "file")) == os.path.join(
            "~", "file"
        )


def test_display_path_root_home(monkeypatch: pytest.MonkeyPatch, root: str) -> None:
    """Verify that a home directory that is the root doesn't change paths.

    Some containers have / as the home directory.
    """

    set_home(monkeypatch, os.path.abspath(os.sep))

    assert display_path(root) == root

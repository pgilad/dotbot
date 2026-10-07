import os
import sys
from collections.abc import Callable
from typing import Any

import pytest

from tests.conftest import Dotfiles


def make_broken_links(root: str, home: str) -> list[str]:
    """Make broken links in home and in its subdirectories.

    The links point outside of the base directory. Returns their paths,
    relative to home.
    """

    os.makedirs(os.path.join(home, "a", "b"))
    names = ["c", os.path.join("a", "d"), os.path.join("a", "b", "e")]
    for name in names:
        os.symlink(os.path.join(root, "nowhere"), os.path.join(home, name))
    return names


def test_clean_options_apply_to_one_directory(
    root: str, home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that the options of a directory don't apply to the next directory."""

    os.symlink(os.path.join(root, "nowhere"), os.path.join(home, ".g"))
    dotfiles.write_config(
        [
            {
                "clean": {
                    "~/nonexistent": {"force": True},
                    "~/": None,
                },
            }
        ]
    )
    run_dotbot()

    assert os.path.islink(os.path.join(home, ".g"))


def test_clean_environment_variable_expansion(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify clean expands environment variables."""

    os.symlink(os.path.join(dotfiles.directory, "f"), os.path.join(home, ".f"))
    variable = "$HOME"
    if sys.platform == "win32":
        variable = "$USERPROFILE"
    dotfiles.write_config([{"clean": [variable]}])
    run_dotbot()

    assert not os.path.islink(os.path.join(home, ".f"))


def test_clean_missing(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify clean deletes broken links that point in the base directory.

    Links that aren't broken stay, and so do broken links that point outside of
    the base directory. The summary line counts both.
    """

    dotfiles.write("f")
    os.symlink(os.path.join(dotfiles.directory, "f"), os.path.join(home, ".f"))
    os.symlink(os.path.join(dotfiles.directory, "g"), os.path.join(home, ".g"))
    os.symlink(os.path.join(home, "h"), os.path.join(home, ".h"))
    dotfiles.write_config([{"clean": ["~"]}])
    run_dotbot()

    assert os.path.islink(os.path.join(home, ".f"))
    assert not os.path.islink(os.path.join(home, ".g"))
    assert os.path.islink(os.path.join(home, ".h"))
    assert (
        "clean: 1 directory checked, 1 invalid link removed, 1 invalid link kept"
        in capfd.readouterr().out.splitlines()
    )


def test_clean_nonexistent(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify clean ignores nonexistent directories, also in the summary line."""

    _ = home
    dotfiles.write_config([{"clean": ["~", "~/fake"]}])
    run_dotbot()  # Nonexistent directories should not raise exceptions.

    assert (
        "clean: 1 directory checked, no invalid links"
        in capfd.readouterr().out.splitlines()
    )


@pytest.mark.parametrize(
    "config",
    [
        pytest.param([{"clean": {"~/": {"force": True}}}], id="option"),
        pytest.param(
            [{"defaults": {"clean": {"force": True}}}, {"clean": ["~"]}],
            id="defaults",
        ),
    ],
)
def test_clean_outside_force(
    config: list[dict[str, Any]],
    root: str,
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that force removes broken links that point outside of the base directory."""

    os.symlink(os.path.join(root, "nowhere"), os.path.join(home, ".g"))
    dotfiles.write_config(config)
    run_dotbot()

    assert not os.path.islink(os.path.join(home, ".g"))


@pytest.mark.parametrize("recursive", [False, True])
def test_clean_recursive(
    recursive: bool,  # noqa: FBT001
    root: str,
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify clean removes the links in subdirectories only if recursive is on."""

    top, *nested = make_broken_links(root, home)
    dotfiles.write_config([{"clean": {"~": {"force": True, "recursive": recursive}}}])
    run_dotbot()

    assert not os.path.islink(os.path.join(home, top))
    for name in nested:
        assert os.path.islink(os.path.join(home, name)) is not recursive


def test_clean_dry_run(
    capfd: pytest.CaptureFixture[str],
    root: str,
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the clean plugin does not delete links during a dry run."""

    names = make_broken_links(root, home)
    dotfiles.write_config([{"clean": {"~": {"force": True, "recursive": True}}}])
    run_dotbot("-n")

    lines = capfd.readouterr().out.splitlines()
    for name in names:
        assert os.path.islink(os.path.join(home, name))
        link = os.path.join("~", name)
        target = os.path.join(root, "nowhere")
        assert f"Would remove invalid link {link} -> {target}" in lines
    assert "clean: 3 directories checked, 3 invalid links to remove" in lines


def test_clean_recursive_does_not_follow_symlinked_directories(
    root: str, home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify recursive clean doesn't descend into symlinked directories.

    A symlinked directory can point outside of the target directory.
    """

    outside = os.path.join(root, "outside")
    os.makedirs(outside)
    os.symlink(
        os.path.join(dotfiles.directory, "nowhere"), os.path.join(outside, "dead")
    )
    os.symlink(outside, os.path.join(home, "linked"), target_is_directory=True)
    dotfiles.write_config([{"clean": {"~": {"recursive": True}}}])
    run_dotbot()

    assert os.path.islink(os.path.join(home, "linked"))
    assert os.path.islink(os.path.join(outside, "dead"))

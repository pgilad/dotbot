import copy
import os
import sys
from collections.abc import Callable

import pytest

from tests.conftest import Dotfiles


@pytest.mark.parametrize("absolute", [False, True])
@pytest.mark.parametrize(
    "directives",
    [
        pytest.param([["file.py", "plugins"]], id="one-directive"),
        pytest.param([["file.py"], ["plugins"]], id="two-directives"),
    ],
)
def test_plugins_directive(
    directives: list[list[str]],
    absolute: bool,  # noqa: FBT001
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the plugins directive loads plugin files and directories.

    A path can be relative to the base directory, or absolute.
    """

    dotfiles.copy_plugin("file", "file.py")
    dotfiles.copy_plugin("directory", os.path.join("plugins", "directory.py"))
    if absolute:
        directives = [
            [os.path.join(dotfiles.directory, path) for path in paths]
            for paths in directives
        ]
    dotfiles.write_config(
        [
            *({"plugins": paths} for paths in directives),
            {"plugin_file": "no-check-context"},
            {"plugin_directory": "no-check-context"},
        ]
    )
    run_dotbot()

    with open(os.path.join(home, "flag-file")) as file:
        assert file.read() == "file plugin loading works"
    with open(os.path.join(home, "flag-directory")) as file:
        assert file.read() == "directory plugin loading works"


def test_plugin_command_line_and_config(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that plugins can be simultaneously loaded via command-line arguments and config."""

    dotfiles.copy_plugin("file", "file.py")
    dotfiles.copy_plugin("directory", os.path.join("plugins", "directory.py"))
    dotfiles.write_config(
        [
            {"plugins": ["file.py"]},
            {"plugin_file": "no-check-context"},
            {"plugin_directory": "no-check-context"},
        ]
    )
    run_dotbot("--plugin-dir", os.path.join(dotfiles.directory, "plugins"))

    with open(os.path.join(home, "flag-file")) as file:
        assert file.read() == "file plugin loading works"
    with open(os.path.join(home, "flag-directory")) as file:
        assert file.read() == "directory plugin loading works"


def test_plugin_nonexistent(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that trying to load a non-existent plugin is an error."""

    dotfiles.write_config(
        [
            {"plugins": ["nonexistent.py"]},
            {"plugin_file": "no-check-context"},
        ]
    )
    with pytest.raises(SystemExit) as excinfo:
        run_dotbot()

    assert excinfo.value.code == 1
    stderr = capfd.readouterr().err.splitlines()
    assert any(
        line.startswith("error: Failed to load plugin 'nonexistent.py': ")
        for line in stderr
    )


def test_plugin_empty_list(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that an empty plugin list doesn't cause errors."""

    dotfiles.write_config(
        [
            {"plugins": []},
            {"link": {"~/test": "test"}},
        ]
    )
    dotfiles.write("test", "content")
    run_dotbot()

    with open(os.path.join(home, "test")) as file:
        assert file.read() == "content"


def test_plugin_duplicate_loading(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that duplicate plugin references don't load/execute the plugin multiple times."""

    dotfiles.copy_plugin("counter", "counter.py")
    dotfiles.write_config(
        [
            {"plugins": ["counter.py", "counter.py"]},
            {"counter": {}},
        ]
    )
    run_dotbot()

    with open(os.path.join(home, "counter")) as file:
        assert file.read() == "1"


def test_plugin_files_with_the_same_name(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that plugin files and classes with the same name all load."""

    for directive in ("apple", "banana"):
        dotfiles.copy_plugin("same_name", os.path.join(directive, "plugin.py"))
    dotfiles.write_config(
        [
            {"plugins": ["apple/plugin.py", "banana/plugin.py"]},
            {"apple": None},
            {"banana": None},
        ]
    )
    run_dotbot()

    for directive in ("apple", "banana"):
        with open(os.path.join(home, directive)) as file:
            assert file.read() == directive


def test_plugin_module_registration(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that plugin modules are in sys.modules, under a private name.

    Some code, such as dataclasses, looks up the module of a class in
    sys.modules. The plugin file is named copy.py, to verify that it doesn't
    replace the copy module of the standard library.
    """

    dotfiles.copy_plugin("dataclass", "copy.py")
    dotfiles.write_config(
        [
            {"plugins": ["copy.py"]},
            {"plugin_dataclass": None},
        ]
    )
    run_dotbot()

    with open(os.path.join(home, "flag-dataclass")) as file:
        assert file.read() == "dataclass plugin loading works"
    assert sys.modules["copy"] is copy


def test_plugin_loading_after_failure(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that an earlier failure doesn't make a later plugin load fail."""

    dotfiles.copy_plugin("file", "file.py")
    dotfiles.write_config(
        [
            {"shell": ["exit 1"]},
            {"plugins": ["file.py"]},
            {"plugin_file": "no-check-context"},
        ]
    )
    with pytest.raises(SystemExit):
        run_dotbot()

    with open(os.path.join(home, "flag-file")) as file:
        assert file.read() == "file plugin loading works"
    assert capfd.readouterr().err.splitlines() == [
        "error: Command [exit 1] failed with exit code 1",
        "error: Failed (1 error, 1 action)",
    ]

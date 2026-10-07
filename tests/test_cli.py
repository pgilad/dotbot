import os
import shutil
import subprocess
import sys
from collections.abc import Callable

import pytest

import dotbot
from dotbot.dispatcher import Dispatcher
from dotbot.plugins import Link, Shell
from tests.conftest import Dotfiles, plugin_file


@pytest.mark.parametrize(
    ("arguments", "skipped"),
    [
        pytest.param(["--only", "create"], {"shell", "link"}, id="only"),
        pytest.param(["--only", "create", "shell"], {"link"}, id="only-multiple"),
        pytest.param(["--except", "create"], {"create"}, id="except"),
        pytest.param(
            ["--except", "create", "shell"], {"create", "shell"}, id="except-multiple"
        ),
    ],
)
def test_only_and_except(
    arguments: list[str],
    skipped: set[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that `--only` and `--except` select the directives that run."""

    dotfiles.write("f")
    dotfiles.write_config(
        [
            {"create": ["~/a"]},
            {"shell": ["echo shell > shell"]},
            {"link": {"~/.f": "f"}},
        ]
    )
    run_dotbot(*arguments)

    assert os.path.isdir(os.path.join(home, "a")) is ("create" not in skipped)
    assert os.path.exists(os.path.join(dotfiles.directory, "shell")) is (
        "shell" not in skipped
    )
    assert os.path.islink(os.path.join(home, ".f")) is ("link" not in skipped)


def test_exit_on_failure(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that processing can halt immediately on failures."""

    dotfiles.write_config(
        [
            {"create": ["~/a"]},
            {"shell": ["this_is_not_a_command"]},
            {"create": ["~/b"]},
        ]
    )
    with pytest.raises(SystemExit):
        run_dotbot("-x")

    assert os.path.isdir(os.path.join(home, "a"))
    assert not os.path.isdir(os.path.join(home, "b"))


def test_only_with_defaults(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that `--only` does not suppress defaults."""

    dotfiles.write_config(
        [
            {"defaults": {"shell": {"stdout": True}}},
            {"create": ["~/a"]},
            {"shell": [{"command": "echo success"}]},
        ]
    )
    run_dotbot("--only", "shell")

    assert not os.path.exists(os.path.join(home, "a"))
    stdout = capfd.readouterr().out.splitlines()
    assert any(line.startswith("success") for line in stdout)


def test_plugin_loading_file(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that plugins can be loaded by file."""

    plugin = dotfiles.copy_plugin("file", "file.py")
    dotfiles.write_config([{"plugin_file": "~"}])
    run_dotbot("--plugin", plugin)

    with open(os.path.join(home, "flag-file")) as file:
        assert file.read() == "file plugin loading works"


def test_plugin_loading_directory(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that plugins can be loaded from a directory."""

    dotfiles.copy_plugin("directory", os.path.join("plugins", "directory.py"))
    dotfiles.write_config([{"plugin_directory": "~"}])
    run_dotbot("--plugin-dir", os.path.join(dotfiles.directory, "plugins"))

    with open(os.path.join(home, "flag-directory")) as file:
        assert file.read() == "directory plugin loading works"


def test_issue_357(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that built-in plugins are only executed once, when
    using a plugin that imports from dotbot.plugins."""

    _ = home
    dotfiles.write_config([{"shell": [{"command": "echo apple", "stdout": True}]}])
    run_dotbot("--plugin", plugin_file("issue_357"))

    lines = [line.strip() for line in capfd.readouterr().out.splitlines()]
    assert lines.count("apple") == 1


def test_disable_builtin_plugins(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that builtin plugins can be disabled."""

    dotfiles.write("f", "apple")
    dotfiles.write_config([{"link": {"~/.f": "f"}}])

    # The link directive will be unhandled so dotbot will raise SystemExit.
    with pytest.raises(SystemExit):
        run_dotbot("--disable-built-in-plugins")

    assert not os.path.exists(os.path.join(home, ".f"))


@pytest.mark.parametrize("plugin", ["context_plugin", "dispatcher_no_plugins"])
def test_plugin_makes_dispatcher(
    plugin: str,
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a plugin can make a Dispatcher that has all the plugins.

    The plugin can give the plugins of its context to the Dispatcher, or give
    no plugins (the behavior before plugins were passed in explicitly).
    """

    _ = home
    dotfiles.write_config(
        [{"dispatch": [{"shell": [{"command": "echo apple", "stdout": True}]}]}]
    )
    run_dotbot("--plugin", dotfiles.copy_plugin(plugin, "plugin.py"))

    stdout = capfd.readouterr().out.splitlines()
    assert any(line.startswith("apple") for line in stdout)


def test_dry_run_unaware_plugin(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that plugins not aware of dry-run mode do not execute actions during a dry run."""

    dotfiles.write_config([{"plugin_file": "~"}])
    run_dotbot("--plugin", dotfiles.copy_plugin("file", "file.py"), "--dry-run")

    assert not os.path.exists(os.path.join(home, "flag-file"))

    stderr = capfd.readouterr().err.splitlines()
    assert "warning: Skipping dry-run-unaware plugin File" in stderr


def test_dry_run_aware_plugin(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that plugins that are aware of dry-run mode do execute during a dry run."""

    dotfiles.write_config([{"dry_run": "~"}])
    run_dotbot("--plugin", dotfiles.copy_plugin("dry_run", "dry_run.py"), "--dry-run")

    assert not os.path.exists(os.path.join(home, "flag-dry-run"))
    stdout = capfd.readouterr().out.splitlines()
    assert any(line.startswith("Would execute dry run") for line in stdout)


def test_only_loads_plugins(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that `--only` doesn't skip the plugins directive."""

    dotfiles.copy_plugin("file", "file.py")
    dotfiles.write_config(
        [
            {"plugins": ["file.py"]},
            {"plugin_file": "no-check-context"},
        ]
    )
    run_dotbot("--only", "plugin_file")

    with open(os.path.join(home, "flag-file")) as file:
        assert file.read() == "file plugin loading works"


def test_plugin_load_error(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a plugin that cannot be loaded gives an error, not a traceback."""

    dotfiles.write_config([])
    with pytest.raises(SystemExit) as excinfo:
        run_dotbot("--plugin", os.path.join(dotfiles.directory, "nonexistent.py"))

    assert excinfo.value.code == 1
    stderr = capfd.readouterr().err
    assert "error: Could not load plugins" in stderr
    assert "Traceback" not in stderr


@pytest.mark.parametrize("argument", ["-q", "-Q"])
def test_quiet(
    argument: str,
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that quiet hides the actions, but not the warnings.

    `-Q` is the deprecated form of `-q`.
    """

    dotfiles.write("f")
    dotfiles.write_config([{"link": {"~/.f": {"path": "f", "unknown": True}}}])
    run_dotbot(argument)

    assert os.path.islink(os.path.join(home, ".f"))
    output = capfd.readouterr()
    assert output.out == ""
    assert output.err.splitlines() == [
        f"warning: Unknown option 'unknown' for {os.path.join('~', '.f')}"
    ]


@pytest.mark.parametrize(
    ("arguments", "error"),
    [
        pytest.param(
            ["--force-color", "--no-color"],
            "`--force-color` and `--no-color` cannot both be provided",
            id="colors",
        ),
        pytest.param([], "No configuration file specified", id="no-config"),
    ],
)
def test_usage_error(
    arguments: list[str],
    error: str,
    capfd: pytest.CaptureFixture[str],
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that wrong arguments give an error."""

    with pytest.raises(SystemExit) as excinfo:
        run_dotbot(*arguments, custom=True)

    assert excinfo.value.code == 1
    assert f"error: {error}" in capfd.readouterr().err


def test_python_m_dotbot() -> None:
    """Verify that `python -m dotbot` works."""

    result = subprocess.run(
        [sys.executable, "-m", "dotbot", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.startswith("Dotbot version")


def test_version_outside_of_checkout(root: str) -> None:
    """Verify that --version shows a git commit only for a checkout of Dotbot.

    An installed Dotbot can be in the git repository of something else, such
    as a home directory under version control.
    """

    if shutil.which("git") is None:
        pytest.skip("git is unavailable")
    repository = os.path.join(root, "repository")
    site_packages = os.path.join(repository, "lib", "site-packages")
    shutil.copytree(
        os.path.dirname(os.path.abspath(dotbot.__file__)),
        os.path.join(site_packages, "dotbot"),
    )
    git_config = os.path.join(root, "gitconfig")
    with open(git_config, "w"):
        pass
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": git_config,
        "GIT_CONFIG_NOSYSTEM": "1",
        "PYTHONPATH": site_packages,
    }
    git = ["git", "-c", "user.name=Dotbot", "-c", "user.email=dotbot@example.com"]
    subprocess.run([*git, "init", "--quiet", repository], check=True, env=env)
    subprocess.run(
        [*git, "-C", repository, "commit", "--quiet", "--allow-empty", "-m", "Commit"],
        check=True,
        env=env,
    )

    result = subprocess.run(
        [sys.executable, "-m", "dotbot", "--version"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    assert result.stdout == f"Dotbot version {dotbot.__version__}\n"


def test_nonexistent_base_directory(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a nonexistent base directory is an error, not an exception."""

    dotfiles.write_config([])
    with pytest.raises(SystemExit) as excinfo:
        run_dotbot("-d", os.path.join(dotfiles.directory, "nonexistent"))

    assert excinfo.value.code == 1
    assert "Could not use base directory:" in capfd.readouterr().err


def test_dispatcher_without_options(home: str, dotfiles: Dotfiles) -> None:
    """Verify that the built-in plugins work in a Dispatcher without options.

    The options of a Dispatcher are optional, and plugins can make their own
    Dispatcher.
    """

    dotfiles.write("f", "apple")
    dispatcher = Dispatcher(dotfiles.directory, plugins=[Link, Shell])

    assert dispatcher.dispatch(
        [{"link": {"~/.f": "f"}}, {"shell": ["echo banana > g"]}]
    )
    with open(os.path.join(home, ".f")) as file:
        assert file.read() == "apple"
    with open(os.path.join(dotfiles.directory, "g")) as file:
        assert file.read().strip() == "banana"


def test_summary(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the last line counts the warnings, changes, and commands of
    each run, and that a command isn't a change."""

    _ = home
    dotfiles.write("f")
    dotfiles.write_config(
        [
            {"link": {"~/.f": {"path": "f", "unknown": True}}},
            {"shell": ["echo apple"]},
        ]
    )

    run_dotbot("--dry-run")
    assert capfd.readouterr().out.splitlines()[-1] == (
        "Dry run done (1 warning, 1 change, 1 command)"
    )
    run_dotbot()
    assert capfd.readouterr().out.splitlines()[-1] == (
        "Done (1 warning, 1 change, 1 command)"
    )
    run_dotbot()
    assert capfd.readouterr().out.splitlines()[-1] == (
        "Done (1 warning, no changes, 1 command)"
    )


@pytest.mark.parametrize(
    ("arguments", "summary"),
    [
        ([], "Failed (1 error, 1 change)"),
        (["-x"], "Stopped after the first failed directive (1 error, no changes)"),
    ],
)
def test_summary_failure(
    arguments: list[str],
    summary: str,
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a failed item is one error, and the last line counts the errors."""

    _ = home
    dotfiles.write("f")
    dotfiles.write_config(
        [{"link": {"~/.missing": "missing"}}, {"link": {"~/.f": "f"}}]
    )
    with pytest.raises(SystemExit):
        run_dotbot(*arguments)

    assert capfd.readouterr().err.splitlines() == [
        f"error: Nonexistent target {os.path.join('~', '.missing')} -> missing",
        f"error: {summary}",
    ]


def test_plugin_failure_without_error(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a plugin that fails without an error message gets one."""

    dotfiles.write_config([{"fail": None}])
    with pytest.raises(SystemExit):
        run_dotbot("--plugin", dotfiles.copy_plugin("fail", "fail.py"))

    assert capfd.readouterr().err.splitlines() == [
        "error: Action fail failed",
        "error: Failed (1 error, no changes)",
    ]


def test_color_output(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify the colors of the levels, and that color keeps the level words.

    Without the words, the level is lost when the color is (for example, in a
    copied log, or for a reader who can't see the color).
    """

    _ = home
    dotfiles.write("f")
    # create logs a debug message for the parent directory
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/d/f": {"path": "f", "create": True, "unknown": True},
                    "~/.missing": "missing",
                }
            }
        ]
    )
    with pytest.raises(SystemExit):
        run_dotbot("--force-color", "-vv")

    output = capfd.readouterr()
    stderr = output.err.splitlines()
    stdout = output.out.splitlines()
    link = os.path.join("~", "d", "f")
    assert f"\033[93mwarning: Unknown option 'unknown' for {link}\033[0m" in stderr
    assert "\033[91merror: Failed (1 error, 1 warning, 2 changes)\033[0m" in stderr
    assert any(line.startswith("\033[92mCreating symlink ") for line in stdout)
    assert any(line.startswith("\033[90m") for line in stdout)

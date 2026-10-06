import os
import shutil
import subprocess
import sys
from collections.abc import Callable

import pytest

import dotbot
from dotbot.dispatcher import Dispatcher
from dotbot.plugins import Link, Shell
from tests.conftest import Dotfiles


def test_except_create(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that `--except` works as intended."""

    dotfiles.write_config(
        [
            {"create": ["~/a"]},
            {
                "shell": [
                    {"command": "echo success", "stdout": True},
                ]
            },
        ]
    )
    run_dotbot("--except", "create")

    assert not os.path.exists(os.path.join(home, "a"))
    stdout = capfd.readouterr().out.splitlines()
    assert any(line.startswith("success") for line in stdout)


def test_except_shell(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that `--except` works as intended."""

    dotfiles.write_config(
        [
            {"create": ["~/a"]},
            {
                "shell": [
                    {"command": "echo failure", "stdout": True},
                ]
            },
        ]
    )
    run_dotbot("--except", "shell")

    assert os.path.exists(os.path.join(home, "a"))
    stdout = capfd.readouterr().out.splitlines()
    assert not any(line.startswith("failure") for line in stdout)


def test_except_multiples(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that `--except` works with multiple exceptions."""

    dotfiles.write_config(
        [
            {"create": ["~/a"]},
            {
                "shell": [
                    {"command": "echo failure", "stdout": True},
                ]
            },
        ]
    )
    run_dotbot("--except", "create", "shell")

    assert not os.path.exists(os.path.join(home, "a"))
    stdout = capfd.readouterr().out.splitlines()
    assert not any(line.startswith("failure") for line in stdout)


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


def test_only(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that `--only` works as intended."""

    dotfiles.write_config(
        [
            {"create": ["~/a"]},
            {"shell": [{"command": "echo success", "stdout": True}]},
        ]
    )
    run_dotbot("--only", "shell")

    assert not os.path.exists(os.path.join(home, "a"))
    stdout = capfd.readouterr().out.splitlines()
    assert any(line.startswith("success") for line in stdout)


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


def test_only_with_multiples(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that `--only` works as intended."""

    dotfiles.write_config(
        [
            {"create": ["~/a"]},
            {"shell": [{"command": "echo success", "stdout": True}]},
            {"link": ["~/.f"]},
        ]
    )
    run_dotbot("--only", "create", "shell")

    assert os.path.isdir(os.path.join(home, "a"))
    stdout = capfd.readouterr().out.splitlines()
    assert any(line.startswith("success") for line in stdout)
    assert not os.path.exists(os.path.join(home, ".f"))


def test_plugin_loading_file(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that plugins can be loaded by file."""

    plugin_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "dotbot_plugin_file.py"
    )
    shutil.copy(plugin_file, os.path.join(dotfiles.directory, "file.py"))
    dotfiles.write_config([{"plugin_file": "~"}])
    run_dotbot("--plugin", os.path.join(dotfiles.directory, "file.py"))

    with open(os.path.join(home, "flag-file")) as file:
        assert file.read() == "file plugin loading works"


def test_plugin_loading_directory(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that plugins can be loaded from a directory."""

    dotfiles.makedirs("plugins")
    plugin_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "dotbot_plugin_directory.py"
    )
    shutil.copy(
        plugin_file, os.path.join(dotfiles.directory, "plugins", "directory.py")
    )
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
    plugin_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "dotbot_plugin_issue_357.py"
    )
    dotfiles.write_config([{"shell": [{"command": "echo apple", "stdout": True}]}])

    run_dotbot("--plugin", plugin_file)

    assert (
        len(
            [
                line
                for line in capfd.readouterr().out.splitlines()
                if line.strip() == "apple"
            ]
        )
        == 1
    )


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


def test_plugin_context_plugin(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the plugin context is available to plugins."""

    _ = home
    plugin_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "dotbot_plugin_context_plugin.py"
    )
    shutil.copy(plugin_file, os.path.join(dotfiles.directory, "plugin.py"))
    dotfiles.write_config(
        [{"dispatch": [{"shell": [{"command": "echo apple", "stdout": True}]}]}]
    )
    run_dotbot("--plugin", os.path.join(dotfiles.directory, "plugin.py"))

    stdout = capfd.readouterr().out.splitlines()
    assert any(line.startswith("apple") for line in stdout)


def test_plugin_dispatcher_no_plugins(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that plugins instantiating Dispatcher without plugins work."""

    _ = home
    plugin_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "dotbot_plugin_dispatcher_no_plugins.py",
    )
    shutil.copy(plugin_file, os.path.join(dotfiles.directory, "plugin.py"))
    dotfiles.write_config(
        [{"dispatch": [{"shell": [{"command": "echo apple", "stdout": True}]}]}]
    )
    run_dotbot("--plugin", os.path.join(dotfiles.directory, "plugin.py"))

    stdout = capfd.readouterr().out.splitlines()
    assert any(line.startswith("apple") for line in stdout)


def test_dry_run_unaware_plugin(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that plugins not aware of dry-run mode do not execute actions during a dry run."""

    plugin_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "dotbot_plugin_file.py"
    )
    shutil.copy(plugin_file, os.path.join(dotfiles.directory, "file.py"))
    dotfiles.write_config([{"plugin_file": "~"}])
    run_dotbot("--plugin", os.path.join(dotfiles.directory, "file.py"), "--dry-run")

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

    plugin_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "dotbot_plugin_dry_run.py"
    )
    shutil.copy(plugin_file, os.path.join(dotfiles.directory, "dry_run.py"))
    dotfiles.write_config([{"dry_run": "~"}])
    run_dotbot("--plugin", os.path.join(dotfiles.directory, "dry_run.py"), "--dry-run")

    assert not os.path.exists(os.path.join(home, "flag-dry-run"))
    stdout = capfd.readouterr().out.splitlines()
    assert any(line.startswith("Would execute dry run") for line in stdout)


def test_dry_run_aware_plugin_no_dry_run(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that plugins that are aware of dry-run mode do execute without dry run."""

    plugin_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "dotbot_plugin_dry_run.py"
    )
    shutil.copy(plugin_file, os.path.join(dotfiles.directory, "dry_run.py"))
    dotfiles.write_config([{"dry_run": "~"}])
    run_dotbot("--plugin", os.path.join(dotfiles.directory, "dry_run.py"))
    with open(os.path.join(home, "flag-dry-run")) as file:
        assert file.read() == "Dry run executed"


def test_only_loads_plugins(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that `--only` doesn't skip the plugins directive."""

    plugin_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "dotbot_plugin_file.py"
    )
    shutil.copy(plugin_file, os.path.join(dotfiles.directory, "file.py"))
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
    """Verify that the last line counts the warnings and actions of each run."""

    _ = home
    dotfiles.write("f")
    dotfiles.write_config([{"link": {"~/.f": {"path": "f", "unknown": True}}}])

    run_dotbot("--dry-run")
    assert capfd.readouterr().out.splitlines()[-1] == (
        "Dry run done (1 warning, 1 action)"
    )
    run_dotbot()
    assert capfd.readouterr().out.splitlines()[-1] == "Done (1 warning, 1 action)"
    run_dotbot()
    assert capfd.readouterr().out.splitlines()[-1] == "Done (1 warning)"


@pytest.mark.parametrize(
    ("arguments", "summary"),
    [
        ([], "Failed (1 error, 1 action)"),
        (["-x"], "Stopped after the first failed directive (1 error)"),
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

    plugin_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "dotbot_plugin_fail.py"
    )
    shutil.copy(plugin_file, os.path.join(dotfiles.directory, "fail.py"))
    dotfiles.write_config([{"fail": None}])
    with pytest.raises(SystemExit):
        run_dotbot("--plugin", os.path.join(dotfiles.directory, "fail.py"))

    assert capfd.readouterr().err.splitlines() == [
        "error: Action fail failed",
        "error: Failed (1 error)",
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
    assert "\033[91merror: Failed (1 error, 1 warning, 2 actions)\033[0m" in stderr
    assert any(line.startswith("\033[92mCreating symlink ") for line in stdout)
    assert any(line.startswith("\033[90m") for line in stdout)

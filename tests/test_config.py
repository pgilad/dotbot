import json
import os
from collections.abc import Callable
from typing import Any

import pytest

from tests.conftest import Dotfiles


@pytest.mark.parametrize("document", ["[]", ""])
def test_config_without_tasks(
    capfd: pytest.CaptureFixture[str],
    document: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that an empty list and an empty file are valid configs."""

    dotfiles.write("config.yaml", document)
    run_dotbot("-c", os.path.join(dotfiles.directory, "config.yaml"), custom=True)

    stderr = capfd.readouterr().err
    assert "warning: No tasks given in configuration, no work to do" in stderr


def test_json_tabs(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that JSON configs are read as JSON, which allows tabs (YAML doesn't)."""

    document = """[\n\t{\n\t\t"create": ["~/d"]\n\t}\n]"""
    dotfiles.write("config.json", document)
    run_dotbot("-c", os.path.join(dotfiles.directory, "config.json"), custom=True)

    assert os.path.isdir(os.path.join(home, "d"))


def test_multiple_config(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that passing multiple configs works."""

    dotfiles.write("config1.json", json.dumps([{"create": ["~/d1"]}]))
    dotfiles.write("config2.json", json.dumps([{"create": ["~/d2"]}]))

    run_dotbot(
        "-c",
        os.path.join(dotfiles.directory, "config1.json"),
        os.path.join(dotfiles.directory, "config2.json"),
        custom=True,
    )

    assert os.path.isdir(os.path.join(home, "d1"))
    assert os.path.isdir(os.path.join(home, "d2"))


@pytest.mark.parametrize(
    ("document", "error"),
    [
        pytest.param(
            "link: {}", "Configuration file must be a list of tasks", id="not-a-list"
        ),
        pytest.param(
            "- link",
            "Each task must be a mapping of actions, but found: 'link'",
            id="not-a-mapping",
        ),
        pytest.param("- link: [", "Could not read config file:", id="syntax-error"),
    ],
)
def test_config_invalid(
    capfd: pytest.CaptureFixture[str],
    document: str,
    error: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that an invalid config gives a clear error."""

    dotfiles.write("config.yaml", document)
    with pytest.raises(SystemExit) as excinfo:
        run_dotbot("-c", os.path.join(dotfiles.directory, "config.yaml"), custom=True)

    assert excinfo.value.code == 1
    assert f"error: {error}" in capfd.readouterr().err


@pytest.mark.parametrize(
    ("config", "warning"),
    [
        (
            [{"link": {"~/.f": {"path": "f", "relnk": True}}}],
            f"Unknown option 'relnk' for {os.path.join('~', '.f')}",
        ),
        (
            [{"defaults": {"link": {"forse": True}}}, {"link": {}}],
            "Unknown option 'forse' in link defaults",
        ),
        ([{"create": {"~/d": {"mod": 0o755}}}], "Unknown option 'mod' for ~/d"),
        (
            [{"shell": [{"command": "exit 0", "stdot": True}]}],
            "Unknown option 'stdot' for shell command",
        ),
        ([{"clean": {"~": {"recursve": True}}}], "Unknown option 'recursve' for ~"),
    ],
)
def test_unknown_options_warn(
    capfd: pytest.CaptureFixture[str],
    config: list[dict[str, Any]],
    warning: str,
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that unknown options cause a warning on stderr.

    Without color, the warning has a prefix that shows its level.
    """

    _ = home
    dotfiles.write("f")
    dotfiles.write_config(config)
    run_dotbot()

    output = capfd.readouterr()
    assert f"warning: {warning}" in output.err
    assert warning not in output.out

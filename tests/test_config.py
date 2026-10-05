import json
import os
from collections.abc import Callable
from typing import Any

import pytest

from tests.conftest import Dotfiles


def test_config_blank(dotfiles: Dotfiles, run_dotbot: Callable[..., None]) -> None:
    """Verify blank configs work."""

    dotfiles.write_config([])
    run_dotbot()


def test_config_empty(dotfiles: Dotfiles, run_dotbot: Callable[..., None]) -> None:
    """Verify empty configs work."""

    dotfiles.write("config.yaml", "")
    run_dotbot("-c", os.path.join(dotfiles.directory, "config.yaml"), custom=True)


def test_json(home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]) -> None:
    """Verify JSON configs work."""

    document = json.dumps([{"create": ["~/d"]}])
    dotfiles.write("config.json", document)
    run_dotbot("-c", os.path.join(dotfiles.directory, "config.json"), custom=True)

    assert os.path.isdir(os.path.join(home, "d"))


def test_json_tabs(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify JSON configs with tabs work."""

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


def test_config_task_not_mapping(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a task that is not a mapping of actions gives a clear error."""

    dotfiles.write_config(["link"])
    with pytest.raises(SystemExit):
        run_dotbot()

    stderr = capfd.readouterr().err
    assert "Each task must be a mapping of actions, but found: 'link'" in stderr


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

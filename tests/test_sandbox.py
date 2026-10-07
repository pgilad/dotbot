import os

import pytest


def test_write_in_root(root: str) -> None:
    """Verify that the sandbox allows writes in the temporary directory."""

    path = os.path.join(root, "abc.txt")
    with open(path, "w") as f:
        f.write("hello")
    with open(path) as f:
        assert f.read() == "hello"


def test_relative_path() -> None:
    """Verify that the sandbox rejects writes to relative paths."""

    with pytest.raises(AssertionError, match="must be an absolute path"):
        open("abc.txt", "w")  # noqa: SIM115

    with pytest.raises(AssertionError, match="must be an absolute path"):
        open(file="abc.txt", mode="w")  # noqa: SIM115

    with pytest.raises(AssertionError, match="must be an absolute path"):
        os.mkdir("a")

    with pytest.raises(AssertionError, match="must be an absolute path"):
        os.mkdir(path="a")


def test_outside_of_root(root: str) -> None:
    """Verify that the sandbox rejects writes outside of the temporary directory."""

    outside = os.path.join(os.path.dirname(root), "outside")

    with pytest.raises(AssertionError, match="must be rooted in"):
        open(outside, "w")  # noqa: SIM115

    with pytest.raises(AssertionError, match="must be rooted in"):
        os.mkdir(outside)

    with pytest.raises(AssertionError, match="must be rooted in"):
        os.symlink(root, outside)

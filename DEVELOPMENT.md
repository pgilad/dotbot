# Development

Dotbot uses the [Hatch] project manager ([installation instructions][hatch-install]).

Hatch automatically manages dependencies and runs testing, type checking, and other operations in isolated [environments][hatch-environments].

[Hatch]: https://hatch.pypa.io/
[hatch-install]: https://hatch.pypa.io/latest/install/
[hatch-environments]: https://hatch.pypa.io/latest/environment/

## Testing

You can run the tests on your local machine with:

```bash
hatch test
```

The [`test` command][hatch-test] supports options such as `-a` for testing with a matrix of Python versions, and appending an argument like `tests/test_shell.py::test_shell_can_override_defaults` for running a single test.

[hatch-test]: https://hatch.pypa.io/latest/tutorials/testing/overview/

### Running Dotbot from a checkout

You can run Dotbot from your checkout, with your changes, in the default Hatch environment:

```bash
hatch run dotbot -c path/to/install.conf.yaml --dry-run
```

### Isolation

Dotbot executes shell commands and interacts with the filesystem, and the tests exercise this functionality. The tests try to [insulate][dotbot-conftest] themselves from the machine, but if you prefer to run tests in an isolated container using Docker, you can do so with the following:

```bash
docker run -it --rm -v "${PWD}:/dotbot" -w /dotbot python:3.14-trixie /bin/bash
```

After spawning the container, install Hatch with `pip install hatch`, and then run the tests as described above.

[dotbot-conftest]: tests/conftest.py

## Type checking

You can run the [mypy static type checker][mypy] with:

```bash
hatch run types:check
```

[mypy]: https://mypy-lang.org/

## Formatting and linting

You can run the [Ruff][ruff] formatter and linter with:

```bash
hatch check fmt --fix
hatch check code --fix
```

This will automatically make [safe fixes][fix-safety] to your code. If you want to only check your files without making modifications, run the commands without `--fix`, as CI does.

[ruff]: https://github.com/astral-sh/ruff
[fix-safety]: https://docs.astral.sh/ruff/linter/#fix-safety

## Demo

The GIF and the screenshot in the README are recorded with [VHS] (`brew install vhs`). After a change to the output of Dotbot, record them again from the root of the repository:

```bash
vhs docs/demo/demo.tape
vhs docs/demo/dry-run.tape
```

The tapes run Dotbot from your checkout, in a temporary home directory that [`docs/demo/setup.sh`][demo-setup] makes. They need uv and git.

[VHS]: https://github.com/charmbracelet/vhs
[demo-setup]: docs/demo/setup.sh

## Packaging

You can use [`hatch build`][hatch-build] to create build artifacts, a [source distribution ("sdist")][sdist] and a [built distribution ("wheel")][bdist].

Dotbot isn't published to PyPI, because the name `dotbot` on PyPI belongs to a different project. The [releases] on GitHub have the build artifacts.

[hatch-build]: https://hatch.pypa.io/latest/build/
[sdist]: https://packaging.python.org/en/latest/glossary/#term-Source-Distribution-or-sdist
[bdist]: https://packaging.python.org/en/latest/glossary/#term-Built-Distribution
[releases]: https://github.com/pgilad/dotbot/releases

## Releasing

1. Set the version in [`src/dotbot/__about__.py`][about].
2. For a new minor or major version, such as 2.1.0, add an entry for it (`- v2.1`) at the top of [`CHANGELOG.md`][changelog]. A patch version doesn't need an entry.
3. Commit the changes, and push them to `main`.
4. Create a tag for the version, such as `v2.1.0`, and push it.

The [release workflow][release] then runs the tests, makes sure that the tag agrees with the version and that the changelog has an entry for a minor or major version, and creates a GitHub release. The release has the changelog entry, the generated notes, the wheel, and the sdist.

[about]: src/dotbot/__about__.py
[changelog]: CHANGELOG.md
[release]: .github/workflows/release.yml

## Continuous integration

Testing, type checking, formatting/linting, and the installation of the built wheel as a uv tool are [checked in CI][ci].

[ci]: .github/workflows/ci.yml

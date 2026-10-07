# Contributing

Bug reports, feature requests, and patches are welcome as [issues] and [pull requests]. Before you work on a large change, open an issue to discuss it. In a bug report, include the Dotbot version (`dotbot --version`), the operating system, the configuration file, and the error messages.

## Development

Dotbot uses the [Hatch] project manager. Hatch installs the dependencies and runs each tool in an isolated [environment][hatch-environments].

```sh
hatch test                 # run the tests; -a for all the Python versions
hatch run types:check      # check the types with mypy
hatch check fmt --fix      # format with Ruff
hatch check code --fix     # lint with Ruff
hatch build                # build the wheel and the sdist into dist/
hatch run dotbot -c path/to/install.conf.yaml --dry-run  # run Dotbot from the checkout
```

To run one test, add its ID, such as `hatch test tests/test_shell.py::test_shell_can_override_defaults`. [CI][ci] runs these checks without `--fix`.

The tests run shell commands and change files. [`tests/conftest.py`][conftest] keeps them in a temporary directory, and makes a test fail if it writes to a different location.

## Demo

The GIF and the screenshot in the README are recorded with [VHS] (`brew install vhs`). After a change to the output of Dotbot, record them again from the root of the repository:

```sh
vhs docs/demo/demo.tape
vhs docs/demo/dry-run.tape
```

The tapes need uv and git. [`docs/demo/setup.sh`][demo-setup] runs Dotbot from the checkout in a temporary home directory.

## Releasing

Dotbot isn't on PyPI, because the name `dotbot` on PyPI belongs to a different project. The [GitHub releases][releases] have the wheel and the sdist.

1. Set the version in [`src/dotbot/__about__.py`][about].
2. For a new minor or major version, such as 2.1.0, add an entry for it (`- v2.1`) at the top of [`CHANGELOG.md`][changelog]. A patch version doesn't need an entry.
3. Commit the changes, and push them to `main`.
4. Create a tag for the version, such as `v2.1.0`, and push it.

The [release workflow][release] runs the tests, makes sure that the tag agrees with the version and that the changelog has an entry for a minor or major version, and creates a GitHub release. The release has the changelog entry, the generated notes, the wheel, and the sdist.

[issues]: https://github.com/pgilad/dotbot/issues
[pull requests]: https://github.com/pgilad/dotbot/pulls
[Hatch]: https://hatch.pypa.io/
[hatch-environments]: https://hatch.pypa.io/latest/environment/
[ci]: .github/workflows/ci.yml
[conftest]: tests/conftest.py
[VHS]: https://github.com/charmbracelet/vhs
[demo-setup]: docs/demo/setup.sh
[releases]: https://github.com/pgilad/dotbot/releases
[about]: src/dotbot/__about__.py
[changelog]: CHANGELOG.md
[release]: .github/workflows/release.yml

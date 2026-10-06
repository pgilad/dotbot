Note: this changelog only lists feature additions, not bugfixes. For details on those, see the Git history.

- v3.0
    - Install Dotbot as an application with `uv tool install git+https://github.com/pgilad/dotbot`; remove `bin/dotbot`, `bin/dotbot.ps1`, and the install scripts for git submodules and Mercurial subrepos
    - Attach the wheel and the source distribution to GitHub releases
- v2.0
    - Require Python 3.14+: `bin/dotbot` and `bin/dotbot.ps1` use uv to find or download Python 3.14+ if it isn't installed
    - Run `shell` commands and `if:` tests with `/bin/sh` (`cmd.exe` on Windows) instead of `$SHELL`
    - Add `executable:` option for `shell`
    - Add `copy` type for `link`
    - Print warnings and errors to stderr
    - Warn about unknown options, undefined environment variables, and globs that match nothing

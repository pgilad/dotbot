# Dotbot [![Build Status](https://github.com/pgilad/dotbot/actions/workflows/ci.yml/badge.svg)](https://github.com/pgilad/dotbot/actions/workflows/ci.yml)

Dotbot makes installing your dotfiles as easy as `dotbot -c install.conf.yaml`, even on a freshly installed system!

- [Rationale](#rationale)
- [Getting Started](#getting-started)
- [Installing Your Dotfiles](#installing-your-dotfiles)
- [Configuration](#configuration)
- [Directives](#directives) ([Link](#link), [Create](#create), [Shell](#shell), [Clean](#clean), [Defaults](#defaults))
- [Plugins](#plugins)
- [Command-line Arguments](#command-line-arguments)

---

## Rationale

Dotbot is a tool that bootstraps your dotfiles (it's a [Dot]files [bo]o[t]strapper, get it?). It does *less* than you think, because version control systems do more than you think.

Dotbot is designed to be lightweight, and its only dependency is PyYAML. Dotbot can also be a drop-in replacement for any other tool you were using to manage your dotfiles, and Dotbot is VCS-agnostic &mdash; it doesn't make any attempt to manage your dotfiles.

Dotbot has many plugins that extend its functionality, such as:

- Secrets management: [dotbot-age](https://github.com/fcatuhe/dotbot-age), [dotbot-gitcrypt](https://gitlab.com/gnfzdz/dotbot-gitcrypt), &mldr;
- Package management: [dotbot-brew](https://github.com/d12frosted/dotbot-brew), [dotbot-apt](https://github.com/bryant1410/dotbot-apt), [dotbot-yum](https://gitlab.com/flyingchipmunk/dotbot-yum), &mldr;
- OS and application configuration: [crontab-dotbot](https://github.com/fundor333/crontab-dotbot), [dotbot-firefox](https://github.com/kurtmckee/dotbot-firefox), &mldr;

## Getting started

### Installation

Dotbot is a command-line application. Install it with [uv], which also downloads Python 3.14+ if it isn't installed:

```bash
uv tool install git+https://github.com/pgilad/dotbot
```

To install a specific [release][releases], add its tag to the URL, for example `git+https://github.com/pgilad/dotbot@v2.0.0`. To upgrade Dotbot, run `uv tool upgrade dotbot`.

Dotbot isn't on PyPI. The `dotbot` package on PyPI is a different project.

On Windows, Dotbot requires that your account is [allowed to create symbolic links][windows-symlinks].

### Set up your dotfiles

Create an empty configuration file in your dotfiles directory:

```bash
cd ~/.dotfiles # replace with the path to your dotfiles
touch install.conf.yaml
```

To get started, you just need to fill in the `install.conf.yaml` and Dotbot will take care of the rest. To help you get started we have [an example](#full-example) config file as well as [configuration documentation](#configuration) for the accepted parameters. Then run Dotbot with your configuration file:

```bash
dotbot -c install.conf.yaml
```

Paths in the configuration file are relative to the *base directory*, which is the directory of the (first) configuration file. You can change the base directory with `-d`.

You can also add an `install` script to your dotfiles, so that a new machine needs only uv. The script runs Dotbot without installing it:

```sh
#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
exec uvx --from git+https://github.com/pgilad/dotbot dotbot -c install.conf.yaml "$@"
```

Add a release tag to the URL to always use the same version of Dotbot.

### Full example

Here's an example of a complete configuration.

The conventional name for the configuration file is `install.conf.yaml`.

```yaml
- defaults:
    link:
      relink: true

- clean: ['~']

- link:
    ~/.tmux.conf: tmux.conf
    ~/.vim: vim
    ~/.vimrc: vimrc

- create:
    - ~/downloads
    - ~/.vim/undo-history

- shell:
  - [git submodule update --init --recursive, Installing submodules]
```

The configuration file is typically written in YAML, but it can also be written in JSON (which is a [subset of YAML][json2yaml]). JSON configuration files are conventionally named `install.conf.json`.

## Installing Your Dotfiles

To install your dotfiles on a new machine, [install Dotbot](#installation), and then:

```bash
git clone <your-dotfiles-repo-url> ~/.dotfiles
cd ~/.dotfiles
dotbot -c install.conf.yaml
```

To update an existing installation:

```bash
cd ~/.dotfiles
git pull
dotbot -c install.conf.yaml
```

## Configuration

Dotbot uses YAML or JSON-formatted configuration files to let you specify how to set up your dotfiles. Currently, Dotbot knows how to [link](#link) files and folders, [create](#create) folders, execute [shell](#shell) commands, and [clean](#clean) directories of broken symbolic links. Dotbot also supports user [plugins](#plugins) for custom commands.

**Ideally, bootstrap configurations should be idempotent. That is, the installer should be able to be run multiple times without causing any problems.** This makes a lot of things easier to do (in particular, syncing updates between machines becomes really easy).

Dotbot configuration files are arrays of tasks, where each task is a dictionary that contains a command name mapping to data for that command. Tasks are run in the order in which they are specified. Commands within a task do not have a defined ordering.

When writing nested constructs, keep in mind that YAML is whitespace-sensitive. Following the formatting used in the examples is a good idea. If a YAML configuration file is not behaving as you expect, try inspecting the [equivalent JSON][json2yaml] and check that it is correct.

## Directives

Most Dotbot commands support both a simplified and extended syntax, and they can also be configured via setting [defaults](#defaults).

### Link

Link commands create symbolic links at specified locations that point to files in your dotfiles repository. This allows you to keep your configuration files in version control while having them appear where applications expect to find them. Symlinks are created by default, but hardlinks and copies are also supported. If desired, items can be specified to be forcibly linked, overwriting existing files if necessary. Environment variables in paths are automatically expanded; if a variable is undefined, Dotbot shows a warning and uses the path as written.

#### Format

Link commands are specified as a dictionary mapping link names to targets. The link name (key) is where the symbolic link will be created, and the target (value) is the file in your dotfiles directory that the link will point to. Targets are specified relative to the base directory (that is specified when running the installer). If linking directories, *do not* include a trailing slash.

Link commands support an optional extended configuration. In this type of configuration, instead of specifying targets directly, link names are mapped to extended configuration dictionaries.

| Parameter | Explanation |
| --- | --- |
| `path` | The target for the link (file in dotfiles directory), the same as in the shortcut syntax (default: null, automatic (see below)) |
| `type` | The type of link to create. If specified, must be `symlink`, `hardlink`, or `copy` (see [copies](#copies)). (default: `symlink`) |
| `create` | When true, create parent directories to the link as needed. (default: false) |
| `relink` | Removes the old link if it's a symlink (default: false) |
| `force` | Force removes the old link, file or folder, and forces a new link (default: false) |
| `backup` | Backup existing files/directories if they exist, creating a backup with suffix `.dotbot-backup.{timestamp}` (default: false) |
| `relative` | When creating a symlink, use a relative path to the target. (default: false, absolute links) |
| `canonicalize` | Resolve any symbolic links encountered in the target to symlink to the canonical path (default: true, real paths) |
| `if` | Execute this with `/bin/sh` (`cmd.exe` on Windows) and only link if it is successful. |
| `ignore-missing` | Do not fail if the target is missing and create the link anyway, and do not warn if a glob matches nothing (default: false) |
| `glob` | Treat `path` as a glob pattern, expanding patterns referenced below, linking all *files* matched. (default: false) |
| `exclude` | Array of glob patterns to remove from glob matches. Uses same syntax as `path`. Ignored if `glob` is `false`. (default: empty, keep all matches) |
| `prefix` | Prepend prefix prefix to basename of each file when linked, when `glob` is `true`. (default: '') |

When `glob: true`, Dotbot uses [glob.glob](https://docs.python.org/3/library/glob.html#glob.glob) to resolve glob paths, expanding Unix shell-style wildcards, which are **not** the same as regular expressions; Only the following are expanded:

| Pattern  | Meaning                            |
|:---------|:-----------------------------------|
| `*`      | matches anything                   |
| `**`     | matches any **file**, recursively  |
| `?`      | matches any single character       |
| `[seq]`  | matches any character in `seq`     |
| `[!seq]` | matches any character not in `seq` |

However, due to the design of `glob.glob`, using a glob pattern such as `config/*`, will **not** match items that begin with `.`. To specifically capture items that being with `.`, you will need to include the `.` in the pattern, like this: `config/.*`.

When using glob with the `exclude:` option, the paths in the exclude paths should be relative to the base directory, same as the glob pattern itself. For example, if a glob pattern `vim/*` matches directories `vim/autoload`, `vim/ftdetect`, `vim/ftplugin`, and `vim/spell`, and you want to ignore the spell directory, then you should use `exclude: ["vim/spell"]` (not just `"spell"`).

#### Copies

With `type: copy`, Dotbot copies the target instead of linking it. This is useful for programs that don't work with symbolic links, and for files that you want to start from a template and then change locally.

- If the copy doesn't exist, Dotbot creates it.
- If the copy exists and is the same as the target, Dotbot does nothing.
- If the copy exists and differs from the target, Dotbot keeps it, so that local changes aren't lost. With `force: true`, Dotbot updates the copy; with `backup: true`, Dotbot first moves the old copy to a backup and then copies the target.
- Dotbot copies a directory file by file, and keeps files that exist only in the copy. When Dotbot updates a copy, it replaces the symbolic links in the copy instead of writing through them.
- If a symbolic link is where the copy should be, Dotbot replaces it only with `relink: true` or `force: true`.
- If a file is where a directory copy should be, or a directory is where a file copy should be, Dotbot shows a warning and keeps it, unless `force: true` or `backup: true` is set.

The `relative` and `canonicalize` options have no effect on copies.

```yaml
- link:
    ~/.gitconfig.local:
      type: copy  # copy it once, then keep local changes
      path: git/gitconfig.local.template
    ~/Library/KeyBindings/DefaultKeyBinding.dict:
      type: copy
      force: true  # keep the copy the same as the target
      create: true
      path: macos/DefaultKeyBinding.dict
```

#### Example

```yaml
- link:
    ~/.config/terminator:
      create: true
      path: config/terminator
    ~/.vim: vim
    ~/.vimrc:
      relink: true
      path: vimrc
    ~/.zshrc:
      force: true
      path: zshrc
    ~/.hammerspoon:
      if: '[ `uname` = Darwin ]'
      path: hammerspoon
    ~/.config/:
      glob: true
      path: dotconf/config/**
    ~/:
      glob: true
      path: dotconf/*
      prefix: '.'
```

If the target location is omitted or set to `null`, Dotbot will use the basename of the link name, with a leading `.` stripped if present. This makes the following two config files equivalent.

Explicit targets:

```yaml
- link:
    ~/bin/ack: ack
    ~/.vim: vim
    ~/.vimrc:
      relink: true
      path: vimrc
    ~/.zshrc:
      force: true
      path: zshrc
    ~/.config/:
      glob: true
      path: config/*
      relink: true
      exclude: [ config/Code ]
    ~/.config/Code/User/:
      create: true
      glob: true
      path: config/Code/User/*
      relink: true
```

Implicit targets:

```yaml
- link:
    ~/bin/ack:
    ~/.vim:
    ~/.vimrc:
      relink: true
    ~/.zshrc:
      force: true
    ~/.config/:
      glob: true
      path: config/*
      relink: true
      exclude: [ config/Code ]
    ~/.config/Code/User/:
      create: true
      glob: true
      path: config/Code/User/*
      relink: true
```

### Create

Create commands specify empty directories to be created.  This can be useful for scaffolding out folders or parent folder structure required for various apps, plugins, shell commands, etc.

#### Format

Create commands are specified as an array of directories to be created. If you want to use the optional extended configuration, create commands are specified as dictionaries. For convenience, it's permissible to leave the options blank (null) in the dictionary syntax.

| Parameter | Explanation |
| --- | --- |
| `mode` | The file mode to use for creating the leaf directory (default: 0777) |

The `mode` parameter is treated in the same way as in Python's [os.mkdir](https://docs.python.org/3/library/os.html#mkdir-modebits). Its behavior is platform-dependent. On Unix systems, the current umask value is first masked out.

#### Example

```yaml
- create:
    - ~/downloads
    - ~/.vim/undo-history
- create:
    ~/.ssh:
      mode: 0700
    ~/projects:
```

### Shell

Shell commands specify shell commands to be run. Shell commands are run in the base directory (that is specified when running the installer).

Shell commands are run with `/bin/sh` (`cmd.exe` on Windows), not with your login shell, so that a configuration works the same for everyone who uses it. To use a different shell, set the `executable` option (for example, in the [defaults](#defaults)), and Dotbot will run `executable -c command`.

#### Format

Shell commands can be specified in several different ways. The simplest way is just to specify a command as a string containing the command to be run.

Another way is to specify a two element array where the first element is the shell command and the second is an optional human-readable description.

Shell commands support an extended syntax as well, which provides more fine-grained control.

| Parameter | Explanation |
| --- | --- |
| `command` | The command to be run |
| `description` | A human-readable message describing the command (default: null) |
| `quiet` | Show only the description but not the command in log output (default: false) |
| `stdin` | Allow a command to read from standard input (default: false) |
| `stdout` | Show a command's output from stdout (default: false) |
| `stderr` | Show a command's error output from stderr (default: false) |
| `executable` | The shell that runs the command, as `executable -c command`, such as `bash` (default: `/bin/sh`, or `cmd.exe` on Windows) |

Note that `quiet` controls whether the command (a string) is printed in log output, it does not control whether the output from running the command is printed (that is controlled by `stdout` / `stderr`). When a command's `stdin` / `stdout` / `stderr` is not enabled (which is the default), it's connected to `/dev/null`, disabling input and hiding output.

#### Example

```yaml
- shell:
  - chsh -s $(which zsh)
  - [chsh -s $(which zsh), Making zsh the default shell]
  -
    command: read var && echo Your variable is $var
    stdin: true
    stdout: true
    description: Reading and printing variable
    quiet: true
  -
    command: read fail
    stderr: true
```

### Clean

Clean commands specify directories that should be checked for dead symbolic links. These dead links are removed automatically. Only dead links that point to somewhere within the dotfiles directory are removed unless the `force` option is set to `true`.

#### Format

Clean commands are specified as an array of directories to be cleaned.

Clean commands also support an extended configuration syntax.

| Parameter | Explanation |
| --- | --- |
| `force` | Remove dead links even if they don't point to a file inside the dotfiles directory (default: false) |
| `recursive` | Traverse the directory recursively looking for dead links (default: false) |

Note: using the `recursive` option for `~` is not recommended because it will be slow.

#### Example

```yaml
- clean: ['~']

- clean:
    ~/:
      force: true
    ~/.config:
      recursive: true
```

### Defaults

Default options for plugins can be specified so that options don't have to be repeated many times. This can be very useful to use with the link command, for example.

Defaults apply to all commands that come after setting the defaults. Defaults can be set multiple times; each change replaces the defaults with a new set of options.

#### Format

Defaults are specified as a dictionary mapping action names to settings, which are dictionaries from option names to values.

#### Example

```yaml
- defaults:
    link:
      create: true
      relink: true
```

### Plugins

Dotbot also supports custom directives implemented by plugins. Plugins are implemented as subclasses of `dotbot.Plugin`, so they must implement `can_handle()` and `handle()`. The `can_handle()` method should return `True` if the plugin can handle an action with the given name. The `handle()` method should do something and return whether or not it completed successfully.

Plugins should declare support for dry-run with `supports_dry_run = True`, and implement this support by logging what the plugin _would_ do (without doing it) when `Context.dry_run()` is set. Plugins that don't explicitly declare support for dry-run will be skipped when Dotbot is run with `--dry-run`.

All built-in Dotbot directives are written as plugins that are loaded by default, so those can be used as a reference when writing custom plugins.

#### Loading plugins via configuration

You can specify plugins in your configuration file as an array of files or directories (containing plugins) to load:

```yaml
- plugins:
    - dotbot-plugins/dotbot-brew/
    - dotbot-plugins/custom_plugin.py
```

Paths specified in the config file are interpreted relative to the _base directory_.

#### Loading plugins via command line

Plugins can also be loaded using the `--plugin` option. You can use this argument multiple times:

```bash
dotbot --plugin dotbot-plugins/dotbot-brew/ --plugin dotbot-plugins/custom_plugin.py ...
```

Paths specified this way are interpreted relative to the _working directory_ where `dotbot` is invoked.

If you use an `install` script, it is recommended that you add these options to it for consistency across installations.

## Command-line arguments

Dotbot takes a number of command-line arguments; you can run `dotbot --help` to see the full list of options. Here, we highlight a couple that are particularly interesting.

### `--dry-run`

You can call `dotbot -c install.conf.yaml --dry-run`, and Dotbot will explain what it _would_ do, without actually making any changes. This can be helpful for safely testing your configuration. Plugins that don't support dry-run will be skipped.

### `--only`

You can call `dotbot -c install.conf.yaml --only [list of directives]`, such as `--only link`, and Dotbot will only run those sections of the config file.

### `--except`

You can call `dotbot -c install.conf.yaml --except [list of directives]`, such as `--except shell`, and Dotbot will run all the sections of the config file except the ones listed.

## Contributing

Do you have a feature request, bug report, or patch? Great! See [CONTRIBUTING.md][contributing] for information on what you can do about that.

## License

Copyright (c) Anish Athalye and Gilad Peleg. Released under the MIT License. See [LICENSE.md][license] for details.

This project started as a fork of [Dotbot](https://github.com/anishathalye/dotbot) by Anish Athalye.

[uv]: https://docs.astral.sh/uv/
[releases]: https://github.com/pgilad/dotbot/releases
[windows-symlinks]: https://learn.microsoft.com/en-us/windows/security/threat-protection/security-policy-settings/create-symbolic-links
[json2yaml]: https://www.json2yaml.com/
[contributing]: CONTRIBUTING.md
[license]: LICENSE.md

# Configuration

A Dotbot configuration is a list of tasks. Each task maps one or more directives to their data. Dotbot runs the tasks in order; the directives in one task have no defined order.

```yaml
- link:
    ~/.vimrc: vimrc
- shell:
    - git submodule update --init
```

- **Format.** Write the configuration in YAML, or in JSON (a [subset of YAML][json2yaml]). The usual name is `install.conf.yaml` (or `install.conf.json`). YAML is sensitive to whitespace: if a configuration doesn't do what you expect, examine the [equivalent JSON][json2yaml].
- **Base directory.** Relative paths are relative to the *base directory*: the directory of the first configuration file. Use `-d` to change it.
- **Idempotence.** Write configurations that you can run many times without problems. Then, to get changes on a machine, you `git pull` and run Dotbot again.

Most directives have a short syntax and an extended syntax with options. Use [`defaults`](#defaults) to set options for many entries.

Directives: [`link`](#link) · [`create`](#create) · [`shell`](#shell) · [`clean`](#clean) · [`defaults`](#defaults) · [`plugins`](plugins.md)

## Link

`link` puts links in your home directory (or elsewhere) that point to files in your dotfiles. Symbolic links are the default; hard links and [copies](#copies) are also available.

Each key is the link (where the link goes). Each value is the target: a path in your dotfiles, relative to the base directory. To link a directory, don't add a trailing slash. Dotbot expands environment variables in paths; if a variable isn't defined, Dotbot shows a warning and uses the path as written.

```yaml
- link:
    ~/.vim: vim
    ~/.vimrc:
      relink: true
      path: vimrc
    ~/.config/terminator:
      create: true
      path: config/terminator
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

If the target is empty (`null`), Dotbot uses the base name of the link, without a leading `.`:

```yaml
- link:
    ~/.vimrc:      # the same as ~/.vimrc: vimrc
    ~/bin/ack:     # the same as ~/bin/ack: ack
    ~/.zshrc:
      force: true  # the same as path: zshrc
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `path` | The target. | the base name of the link |
| `type` | `symlink`, `hardlink`, or `copy` (see [copies](#copies)). | `symlink` |
| `create` | Create the parent directories of the link if necessary. | `false` |
| `relink` | Replace an existing symbolic link. | `false` |
| `force` | Replace an existing file, directory, or link. | `false` |
| `backup` | Move an existing file or directory to `<name>.dotbot-backup.<timestamp>`, and then link. | `false` |
| `relative` | Make a symbolic link with a relative path. | `false` |
| `canonicalize` | Resolve symbolic links in the target path. | `true` |
| `if` | Link only if this command succeeds. Dotbot runs it with `/bin/sh` (`cmd.exe` on Windows). | |
| `ignore-missing` | Link also if the target doesn't exist, and don't warn when a glob matches nothing. | `false` |
| `glob` | Read `path` as a glob pattern, and link each file that it matches. | `false` |
| `exclude` | Glob patterns to remove from the matches of `glob`. | `[]` |
| `prefix` | With `glob`, add this prefix to the name of each link. | `''` |

### Globs

With `glob: true`, Dotbot expands `path` with Python's [`glob.glob`][glob]. These are shell wildcards, not regular expressions:

| Pattern | Matches |
| --- | --- |
| `*` | any characters |
| `**` | any file, recursively |
| `?` | one character |
| `[seq]` | one character in `seq` |
| `[!seq]` | one character not in `seq` |

- `*` doesn't match names that start with `.`. To match them, include the `.`, for example `config/.*`.
- `exclude` paths are relative to the base directory, like `path`. For example, to remove `vim/spell` from the matches of `vim/*`, use `exclude: [vim/spell]`, not `exclude: [spell]`.

```yaml
- link:
    ~/.config/:
      glob: true
      path: config/*
      relink: true
      exclude: [config/Code]
    ~/.config/Code/User/:
      create: true
      glob: true
      path: config/Code/User/*
      relink: true
```

### Copies

With `type: copy`, Dotbot copies the target instead of linking it. This is useful for programs that don't work with symbolic links, and for files that you want to start from a template and then change locally.

- If the copy doesn't exist, Dotbot creates it.
- If the copy exists and is the same as the target, Dotbot does nothing.
- If the copy exists and differs from the target, Dotbot keeps it, so that local changes aren't lost. With `force: true`, Dotbot updates the copy; with `backup: true`, Dotbot first moves the old copy to a backup and then copies the target.
- Dotbot copies a directory file by file, and keeps files that exist only in the copy. When Dotbot updates a copy, it replaces the symbolic links in the copy instead of writing through them.
- If a symbolic link is where the copy should be, Dotbot replaces it only with `relink: true` or `force: true`.
- If a file is where a directory copy should be, or a directory is where a file copy should be, Dotbot shows an error and keeps it, unless `force: true` or `backup: true` is set.

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

## Create

`create` makes empty directories, for example directories that programs or plugins need. Give a list of directories, or a mapping from directories to options (the options can be empty).

| Option | Description | Default |
| --- | --- | --- |
| `mode` | The mode of the last directory in the path, as for Python's [`os.mkdir`][mkdir]. The result depends on the platform; on Unix, the umask applies. | `0777` |

```yaml
- create:
    - ~/downloads
    - ~/.vim/undo-history
- create:
    ~/.ssh:
      mode: 0700
    ~/projects:
```

## Shell

`shell` runs commands in the base directory. Dotbot runs them with `/bin/sh` (`cmd.exe` on Windows), not with your login shell, so that a configuration works the same for everyone. To use a different shell, set `executable`, for example in [`defaults`](#defaults); Dotbot then runs `executable -c command`.

Give each command as a string, as a `[command, description]` list, or as a mapping with options:

| Option | Description | Default |
| --- | --- | --- |
| `command` | The command to run. | |
| `description` | A message that Dotbot shows when it runs the command. | |
| `quiet` | Show only the description, not the command. | `false` |
| `stdin` | Let the command read from standard input. | `false` |
| `stdout` | Show the output of the command. | `false` |
| `stderr` | Show the error output of the command. | `false` |
| `executable` | The shell that runs the command, such as `bash`. | `/bin/sh` (`cmd.exe` on Windows) |

`quiet` controls only how Dotbot shows the command; `stdout` and `stderr` control the output of the command. If `stdin`, `stdout`, or `stderr` isn't enabled, Dotbot connects it to `/dev/null`. With `-vv`, Dotbot shows the output of all commands.

```yaml
- shell:
    - chsh -s $(which zsh)
    - [chsh -s $(which zsh), Making zsh the default shell]
    - command: read var && echo Your variable is $var
      stdin: true
      stdout: true
      description: Reading and printing variable
      quiet: true
    - command: read fail
      stderr: true
```

## Clean

`clean` removes dead symbolic links from directories. By default, Dotbot removes only dead links that point into the dotfiles directory. Give a list of directories, or a mapping from directories to options:

| Option | Description | Default |
| --- | --- | --- |
| `force` | Also remove dead links that point outside the dotfiles directory. | `false` |
| `recursive` | Look in subdirectories too. This is slow for `~`. | `false` |

```yaml
- clean: ['~']

- clean:
    ~/:
      force: true
    ~/.config:
      recursive: true
```

## Defaults

`defaults` sets the default options of directives, so that you don't write the same options many times. Defaults apply to the tasks that come after them. Each `defaults` task replaces all the defaults from before.

```yaml
- defaults:
    link:
      create: true
      relink: true
    shell:
      executable: bash
```

[json2yaml]: https://www.json2yaml.com/
[glob]: https://docs.python.org/3/library/glob.html#glob.glob
[mkdir]: https://docs.python.org/3/library/os.html#os.mkdir

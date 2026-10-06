import contextlib
import filecmp
import glob
import os
import shutil
import stat
import sys
import tempfile
from datetime import UTC, datetime
from typing import Any

from dotbot.plugin import Plugin
from dotbot.util import shell_command
from dotbot.util.common import (
    display_path,
    error_reason,
    normslash,
    undefined_variable,
    unknown_options,
)


class Link(Plugin):
    """
    Symbolically links (or hardlinks, or copies) dotfiles.
    """

    supports_dry_run = True

    _directive = "link"
    _options = frozenset(
        {
            "backup",
            "canonicalize",
            "canonicalize-path",
            "create",
            "exclude",
            "force",
            "glob",
            "if",
            "ignore-missing",
            "path",
            "prefix",
            "relative",
            "relink",
            "type",
        }
    )
    _types = frozenset({"symlink", "hardlink", "copy"})

    def can_handle(self, directive: str) -> bool:
        return directive == self._directive

    def handle(self, directive: str, data: Any) -> bool:
        if directive != self._directive:
            msg = f"Link cannot handle directive {directive}"
            raise ValueError(msg)
        return self._process_links(data)

    def _process_links(self, links: Any) -> bool:
        success = True
        defaults = self._context.defaults().get("link", {})
        for key in unknown_options(defaults, self._options):
            self._log.warning(f"Unknown option '{key}' in link defaults")

        # Validate the default link type before looping.
        link_type = defaults.get("type", "symlink")
        if link_type not in self._types:
            self._log.error(f"The default link type is not recognized: '{link_type}'")
            return False

        for link_name, target in links.items():
            link_name = os.path.expandvars(normslash(link_name))  # noqa: PLW2901
            relative = defaults.get("relative", False)
            # support old "canonicalize-path" key for compatibility
            canonical_path = defaults.get(
                "canonicalize", defaults.get("canonicalize-path", True)
            )
            link_type = defaults.get("type", "symlink")
            force = defaults.get("force", False)
            relink = defaults.get("relink", False)
            create = defaults.get("create", False)
            use_glob = defaults.get("glob", False)
            backup = defaults.get("backup", False)
            base_prefix = defaults.get("prefix", "")
            test = defaults.get("if", None)
            ignore_missing = defaults.get("ignore-missing", False)
            exclude_paths = defaults.get("exclude", [])
            if isinstance(target, dict):
                # extended config
                for key in unknown_options(target, self._options):
                    self._log.warning(
                        f"Unknown option '{key}' for {display_path(link_name)}"
                    )
                test = target.get("if", test)
                relative = target.get("relative", relative)
                canonical_path = target.get(
                    "canonicalize", target.get("canonicalize-path", canonical_path)
                )
                link_type = target.get("type", link_type)
                if link_type not in self._types:
                    msg = f"The link type is not recognized: '{link_type}'"
                    self._log.error(msg)
                    success = False
                    continue
                force = target.get("force", force)
                relink = target.get("relink", relink)
                create = target.get("create", create)
                use_glob = target.get("glob", use_glob)
                backup = target.get("backup", backup)
                base_prefix = target.get("prefix", base_prefix)
                ignore_missing = target.get("ignore-missing", ignore_missing)
                exclude_paths = target.get("exclude", exclude_paths)
                path = self._default_target(link_name, target.get("path"))
            else:
                path = self._default_target(link_name, target)
            path = normslash(path)
            if test is not None and not self._test_success(test):
                self._log.info(
                    f"Skipping {display_path(link_name)}, because `if: {test}` is false"
                )
                continue
            path = os.path.normpath(os.path.expandvars(os.path.expanduser(path)))
            # check after the test, which can guard a link that uses a variable;
            # only warn, because a file name can contain a literal "$"
            variable = undefined_variable(link_name) or undefined_variable(path)
            if variable is not None:
                self._log.warning(
                    f"Undefined environment variable {variable} in {display_path(link_name)} -> {display_path(path)}"
                    ", using the name as written"
                )
            if use_glob and self._has_glob_chars(path):
                glob_results = self._create_glob_results(path, exclude_paths)
                self._log.debug(f"Globs from '{path}': {glob_results}")
                if not glob_results and not ignore_missing:
                    self._log.warning(
                        f"No files match {display_path(link_name)} -> {display_path(path)}"
                    )
                for glob_full_item in glob_results:
                    # Find common dirname between pattern and the item:
                    glob_dirname = os.path.commonpath([path, glob_full_item])
                    glob_item = (
                        glob_full_item
                        if len(glob_dirname) == 0
                        else glob_full_item[len(glob_dirname) + 1 :]
                    )
                    # Add prefix to basepath, if provided
                    if base_prefix:
                        glob_item = base_prefix + glob_item
                    # where is it going
                    glob_link_name = os.path.join(link_name, glob_item)
                    if create:
                        success &= self._create(glob_link_name)
                    if link_type == "copy":
                        success &= self._copy(
                            glob_full_item,
                            glob_link_name,
                            canonical_path=canonical_path,
                            ignore_missing=ignore_missing,
                            force=force,
                            relink=relink,
                            backup=backup,
                        )
                        continue
                    did_backup = False
                    did_delete = False
                    if backup:
                        did_backup, backup_success = self._backup(glob_link_name)
                        success &= backup_success
                    # we only need to consider force/relink if we didn't do a backup
                    if (force or relink) and not (did_backup and backup_success):
                        did_delete, delete_success = self._delete(
                            glob_full_item,
                            glob_link_name,
                            relative=relative,
                            canonical_path=canonical_path,
                            force=force,
                        )
                        success &= delete_success
                    success &= self._link(
                        glob_full_item,
                        glob_link_name,
                        relative=relative,
                        canonical_path=canonical_path,
                        ignore_missing=ignore_missing,
                        link_type=link_type,
                        assume_gone=(did_backup or did_delete),
                    )
            else:
                if create:
                    success &= self._create(link_name)
                if not ignore_missing and not self._exists(
                    os.path.join(self._context.base_directory(), path)
                ):
                    # we seemingly check this twice (here and in _link) because
                    # if the file doesn't exist and force is True, we don't
                    # want to remove the original (this is tested by test_link_force_leaves_when_nonexistent)
                    success = False
                    self._log.error(
                        f"Nonexistent target {display_path(link_name)} -> {display_path(path)}"
                    )
                    continue
                if link_type == "copy":
                    success &= self._copy(
                        path,
                        link_name,
                        canonical_path=canonical_path,
                        ignore_missing=ignore_missing,
                        force=force,
                        relink=relink,
                        backup=backup,
                    )
                    continue
                did_backup = False
                did_delete = False
                if backup:
                    did_backup, backup_success = self._backup(link_name)
                    success &= backup_success
                # we only need to consider force/relink if we didn't do a backup
                if (force or relink) and not (did_backup and backup_success):
                    did_delete, delete_success = self._delete(
                        path,
                        link_name,
                        relative=relative,
                        canonical_path=canonical_path,
                        force=force,
                    )
                    success &= delete_success
                success &= self._link(
                    path,
                    link_name,
                    relative=relative,
                    canonical_path=canonical_path,
                    ignore_missing=ignore_missing,
                    link_type=link_type,
                    assume_gone=(did_backup or did_delete),
                )
        return success

    def _test_success(self, command: str) -> bool:
        ret = shell_command(command, cwd=self._context.base_directory())
        if ret != 0:
            self._log.debug(f"Test '{command}' returned false")
        return ret == 0

    def _default_target(self, link_name: str, target: str | None) -> str:
        if target is None:
            basename = os.path.basename(link_name)
            if basename.startswith("."):
                return basename[1:]
            return basename
        return target

    def _has_glob_chars(self, path: str) -> bool:
        return any(i in path for i in "?*[")

    def _glob(self, path: str) -> list[str]:
        """
        Wrap `glob.glob` in a python agnostic way, catching errors in usage.
        """
        found = glob.glob(path, recursive=True)
        # normalize paths to ensure cross-platform compatibility
        found = [os.path.normpath(p) for p in found]
        # if using recursive glob (`**`), filter results to return only files:
        if "**" in path and not path.endswith(str(os.sep)):
            self._log.debug(f"Excluding directories from recursive glob: {path}")
            found = [f for f in found if os.path.isfile(f)]
        # return matched results
        return found

    def _create_glob_results(self, path: str, exclude_paths: list[str]) -> list[str]:
        self._log.debug(f"Globbing with pattern: {path}")
        include = self._glob(path)
        self._log.debug(f"Glob found : {include}")
        # filter out any paths matching the exclude globs:
        exclude = []
        for expat in exclude_paths:
            self._log.debug(f"Excluding globs with pattern: {expat}")
            exclude.extend(self._glob(expat))
        self._log.debug(f"Excluded globs from '{path}': {exclude}")
        ret = set(include) - set(exclude)
        return list(ret)

    def _is_link(self, path: str) -> bool:
        """
        Returns true if the path is a symbolic link.
        """
        return os.path.islink(os.path.expanduser(path))

    def _link_target(self, path: str) -> str:
        """
        Returns the target of the symbolic link.
        """
        path = os.path.expanduser(path)
        path = os.readlink(path)
        if sys.platform == "win32" and path.startswith("\\\\?\\"):
            path = path[4:]
        return path

    def _exists(self, path: str) -> bool:
        """
        Returns true if the path exists.
        """
        path = os.path.expanduser(path)
        return os.path.exists(path)

    def _lexists(self, path: str) -> bool:
        """
        Returns true if the path exists (including broken symlinks).
        """
        path = os.path.expanduser(path)
        return os.path.lexists(path)

    def _create(self, path: str) -> bool:
        success = True
        parent = os.path.abspath(os.path.join(os.path.expanduser(path), os.pardir))
        if not self._exists(parent):
            self._log.debug(f"Try to create parent: {parent}")
            if self._context.dry_run():
                self._log.action(f"Would create directory {display_path(parent)}")
                return True
            try:
                os.makedirs(parent)
            except OSError as e:
                self._log.error(
                    f"Failed to create directory {display_path(parent)}: {error_reason(e)}"
                )
                success = False
            else:
                self._log.action(f"Creating directory {display_path(parent)}")
        return success

    def _backup(self, path: str) -> tuple[bool, bool]:
        if self._exists(path) and not self._is_link(path):
            timestamp = datetime.now(UTC).astimezone().strftime("%Y%m%d-%H%M%S")
            backup_name = f"{path}.dotbot-backup.{timestamp}"
            self._log.debug(f"Try to backup file {path} to {backup_name}")
            if self._context.dry_run():
                self._log.action(
                    f"Would backup {display_path(path)} to {display_path(backup_name)}"
                )
                return True, True
            try:
                os.rename(
                    os.path.abspath(os.path.expanduser(path)),
                    os.path.abspath(os.path.expanduser(backup_name)),
                )
            except OSError as e:
                self._log.error(
                    f"Failed to backup file {display_path(path)} to {display_path(backup_name)}: {error_reason(e)}"
                )
                return False, False
            else:
                self._log.action(
                    f"Backed up file {display_path(path)} to {display_path(backup_name)}"
                )
                return True, True
        return False, True

    def _delete(
        self,
        target: str,
        path: str,
        *,
        relative: bool,
        canonical_path: bool,
        force: bool,
    ) -> tuple[bool, bool]:
        success = True
        removed = False
        target = os.path.join(
            self._context.base_directory(canonical_path=canonical_path), target
        )
        fullpath = os.path.abspath(os.path.expanduser(path))
        if (
            self._exists(path)
            and not self._is_link(path)
            and os.path.realpath(fullpath) == target
        ):
            # Special case: The path is not a symlink but resolves to the target anyway.
            # Deleting the path would actually delete the target.
            # This may happen if a parent directory is a symlink.
            self._log.error(
                f"{display_path(path)} appears to be the same file as {display_path(target)}"
            )
            return False, False
        if relative:
            target = self._relative_path(target, fullpath)
        if (self._is_link(path) and self._link_target(path) != target) or (
            self._lexists(path) and not self._is_link(path)
        ):
            if self._context.dry_run():
                # same condition as below: without force, only symlinks are removed
                if os.path.islink(fullpath) or force:
                    self._log.action(f"Would remove {display_path(path)}")
                    removed = True
            else:
                try:
                    if os.path.islink(fullpath):
                        os.unlink(fullpath)
                        removed = True
                    elif force:
                        if os.path.isdir(fullpath):
                            shutil.rmtree(fullpath)
                            removed = True
                        else:
                            os.remove(fullpath)
                            removed = True
                except OSError as e:
                    self._log.error(
                        f"Failed to remove {display_path(path)}: {error_reason(e)}"
                    )
                    success = False
                else:
                    if removed:
                        self._log.action(f"Removing {display_path(path)}")
        return removed, success

    def _relative_path(self, target: str, link_name: str) -> str:
        """
        Returns the relative path to get to the target file from the
        link location.
        """
        link_dir = os.path.dirname(link_name)
        return os.path.relpath(target, link_dir)

    def _link(
        self,
        target: str,
        link_name: str,
        *,
        relative: bool,
        canonical_path: bool,
        ignore_missing: bool,
        link_type: str,
        assume_gone: bool,
    ) -> bool:
        """
        Links link_name to target.

        The caller must ensure that the target exists.

        Returns true if successfully linked files.
        """

        link_path = os.path.abspath(os.path.expanduser(link_name))
        base_directory = self._context.base_directory(canonical_path=canonical_path)
        absolute_target = os.path.join(base_directory, target)
        link_name = os.path.normpath(link_name)
        target_path = (
            self._relative_path(absolute_target, link_path)
            if relative
            else absolute_target
        )

        # we need to use absolute_target below because our cwd is the dotfiles
        # directory, and if target_path is relative, it will be relative to the
        # link directory
        if (
            (not self._lexists(link_name)) or (self._context.dry_run() and assume_gone)
        ) and (ignore_missing or self._exists(absolute_target)):
            if self._context.dry_run():
                self._log.action(
                    f"Would create {link_type} {display_path(link_name)} -> {display_path(target_path)}"
                )
                return True
            try:
                if link_type == "symlink":
                    os.symlink(target_path, link_path)
                else:  # link_type == "hardlink"
                    os.link(absolute_target, link_path)
            except OSError as e:
                self._log.error(
                    f"Linking failed {display_path(link_name)} -> {display_path(target_path)}: {error_reason(e)}"
                )
                return False
            else:
                self._log.action(
                    f"Creating {link_type} {display_path(link_name)} -> {display_path(target_path)}"
                )
                return True

        # Failure case: The link name exists and is a symlink
        if self._is_link(link_name):
            if link_type == "symlink":
                if self._link_target(link_name) == target_path:
                    # Idempotent case: The configured symlink already exists
                    self._log.info(
                        f"Link exists {display_path(link_name)} -> {display_path(target_path)}"
                    )
                    return True

                # The existing symlink isn't pointing at the target.
                # Distinguish between an incorrect symlink and a broken ("invalid") symlink.
                terminology = "Incorrect" if self._exists(link_name) else "Invalid"
                self._log.error(
                    f"{terminology} link {display_path(link_name)} -> {display_path(self._link_target(link_name))}"
                )
                return False

            self._log.error(
                f"{display_path(link_name)} already exists but is a symbolic link, not a hard link"
            )
            return False

        # Failure case: The link name exists
        if (
            link_type == "hardlink"
            and self._exists(absolute_target)
            and os.path.samefile(link_path, absolute_target)
        ):
            # Idempotent case: The configured hardlink already exists
            self._log.info(
                f"Link exists {display_path(link_name)} -> {display_path(target_path)}"
            )
            return True

        found = "directory" if os.path.isdir(link_path) else "file"
        expected = "hard link" if link_type == "hardlink" else "symbolic link"
        self._log.error(
            f"{display_path(link_name)} already exists but is a {found}, not a {expected}"
        )
        return False

    def _copy(
        self,
        target: str,
        link_name: str,
        *,
        canonical_path: bool,
        ignore_missing: bool,
        force: bool,
        relink: bool,
        backup: bool,
    ) -> bool:
        """
        Copies target to link_name.

        An existing copy that is the same as the target is left as it is. A
        copy that differs is also left as it is, because it can have local
        changes, unless force or backup is set: then the copy is updated (after
        a backup moves the old copy away). A directory is copied file by file,
        and files that are only in the copy are kept. A symlink at link_name is
        replaced only if relink or force is set, and so is a file where the
        target is a directory (or the other way around).

        Returns true on success, which includes keeping a copy that differs.
        """

        source = os.path.join(
            self._context.base_directory(canonical_path=canonical_path), target
        )
        destination = os.path.abspath(os.path.expanduser(link_name))
        link_name = os.path.normpath(link_name)
        if not os.path.exists(source):
            if ignore_missing:
                self._log.info(
                    f"Nothing to copy, nonexistent target {display_path(link_name)} -> {display_path(source)}"
                )
                return True
            self._log.error(
                f"Nonexistent target {display_path(link_name)} -> {display_path(source)}"
            )
            return False

        exists = os.path.lexists(destination)
        if exists and os.path.islink(destination):
            if not (relink or force):
                self._log.error(
                    f"{display_path(link_name)} already exists but is a symbolic link, not a copy"
                )
                return False
            if not self._remove(destination, link_name):
                return False
            exists = False
        # a file can't be copied over a directory, or the other way around
        source_is_directory = os.path.isdir(source)
        other_type = exists and source_is_directory != os.path.isdir(destination)
        if other_type and not (force or backup):
            expected, found = (
                ("directory", "file") if source_is_directory else ("file", "directory")
            )
            self._log.error(
                f"{display_path(link_name)} already exists but is a {found}, not a {expected}"
            )
            return False
        if exists and not other_type:
            try:
                differs = self._differs(source, destination)
            except OSError as e:
                self._log.error(
                    f"Failed to compare {display_path(link_name)} with {display_path(source)}: {error_reason(e)}"
                )
                return False
            if not differs:
                self._log.info(
                    f"Copy exists {display_path(link_name)} -> {display_path(source)}"
                )
                return True
            if not (force or backup):
                self._log.info(
                    f"Copy {display_path(link_name)} differs from {display_path(source)}, keeping it"
                )
                return True
        if exists and backup:
            _, backup_success = self._backup(link_name)
            if not backup_success:
                return False
            exists = False
        if exists and other_type:
            if not self._remove(destination, link_name):
                return False
            exists = False

        verb = "update" if exists else "create"
        if self._context.dry_run():
            self._log.action(
                f"Would {verb} copy {display_path(link_name)} -> {display_path(source)}"
            )
            return True
        try:
            if source_is_directory:
                self._copy_directory(source, destination)
            else:
                self._copy_file(source, destination)
        except OSError as e:
            self._log.error(
                f"Copying failed {display_path(link_name)} -> {display_path(source)}: {error_reason(e)}"
            )
            return False
        self._log.action(
            f"{'Updating' if exists else 'Creating'} copy {display_path(link_name)} -> {display_path(source)}"
        )
        return True

    def _copy_file(self, source: str, destination: str) -> None:
        """
        Copies a file like shutil.copy2, but into a temporary file that then
        replaces the destination, so that a failed copy keeps the destination.
        A symlink at the destination is replaced, not followed, which would
        change a file outside of the copy, and so is a read-only file.
        """
        file, temporary = tempfile.mkstemp(
            prefix=f".{os.path.basename(destination)}.dotbot-",
            dir=os.path.dirname(destination),
        )
        os.close(file)
        try:
            shutil.copy2(source, temporary)
            if os.path.islink(destination) or os.path.isdir(destination):
                self._remove_path(destination)
            elif sys.platform == "win32" and os.path.exists(destination):
                # Windows doesn't replace a read-only file
                os.chmod(destination, stat.S_IWRITE)
            os.replace(temporary, destination)
        except BaseException:
            with contextlib.suppress(OSError):
                self._remove_path(temporary)
            raise

    def _copy_directory(self, source: str, destination: str) -> None:
        """
        Copies a directory like shutil.copytree with dirs_exist_ok, so files
        that are only in the destination are kept. Unlike shutil.copytree, it
        replaces a symlink in the destination instead of following it.
        """
        if os.path.islink(destination) or not os.path.isdir(destination):
            self._remove_path(destination)
            os.makedirs(destination)
        for name in os.listdir(source):
            source_path = os.path.join(source, name)
            destination_path = os.path.join(destination, name)
            # follow symlinks in the source, like shutil.copytree does
            if os.path.isdir(source_path):
                self._copy_directory(source_path, destination_path)
            else:
                self._copy_file(source_path, destination_path)
        shutil.copystat(source, destination)

    def _differs(self, source: str, destination: str) -> bool:
        """
        Returns true if a file in source is missing from destination or has
        different contents. Files that are only in destination don't count.
        """
        if not os.path.isdir(source):
            return not os.path.isfile(destination) or not filecmp.cmp(
                source, destination, shallow=False
            )
        if not os.path.isdir(destination):
            return True
        # follow symlinks, like shutil.copytree does
        for directory, _, files in os.walk(source, followlinks=True):
            for name in files:
                source_file = os.path.join(directory, name)
                destination_file = os.path.join(
                    destination, os.path.relpath(source_file, source)
                )
                if not os.path.isfile(destination_file) or not filecmp.cmp(
                    source_file, destination_file, shallow=False
                ):
                    return True
        return False

    def _remove(self, path: str, name: str) -> bool:
        """
        Removes a symlink, file, or directory. Returns true on success.
        """
        if self._context.dry_run():
            self._log.action(f"Would remove {display_path(name)}")
            return True
        try:
            self._remove_path(path)
        except OSError as e:
            self._log.error(f"Failed to remove {display_path(name)}: {error_reason(e)}")
            return False
        self._log.action(f"Removing {display_path(name)}")
        return True

    def _remove_path(self, path: str) -> None:
        """
        Removes the symlink, file, or directory at path, if there is one. A
        symlink is removed, not followed.
        """
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        elif os.path.lexists(path):
            if sys.platform == "win32" and not os.path.islink(path):
                # Windows doesn't remove a read-only file
                os.chmod(path, stat.S_IWRITE)
            os.remove(path)

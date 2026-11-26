import contextlib
import errno
import filecmp
import glob
import os
import shutil
import stat
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from dotbot.plugin import Plugin
from dotbot.util import shell_command
from dotbot.util.common import (
    display_path,
    error_reason,
    normslash,
    undefined_variable,
    unknown_options,
)

# the result of one link
type Outcome = Literal["created", "updated", "in place", "kept", "skipped", "failed"]


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
        results: Counter[Outcome] = Counter()
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
                    results["failed"] += 1
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
            if test is not None:
                if not self._context.evaluate_conditions():
                    self._log.warning(
                        f"Skipping conditional link {display_path(link_name)} during dry run"
                    )
                    results["skipped"] += 1
                    continue
                if not self._test_success(test):
                    self._log.info(
                        f"Skipping {display_path(link_name)}, because `if: {test}` is false"
                    )
                    results["skipped"] += 1
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
                pairs = []
                for match in glob_results:
                    glob_dirname = os.path.commonpath([path, match])
                    glob_item = (
                        match[len(glob_dirname) + 1 :] if glob_dirname else match
                    )
                    pairs.append(
                        (match, os.path.join(link_name, base_prefix + glob_item))
                    )
            else:
                pairs = [(path, link_name)]

            for target_path, destination in pairs:
                if create and not self._create(destination):
                    results["failed"] += 1
                    continue
                if link_type == "copy":
                    outcome = self._copy(
                        target_path,
                        destination,
                        canonical_path=canonical_path,
                        ignore_missing=ignore_missing,
                        force=force,
                        relink=relink,
                        backup=backup,
                    )
                else:
                    outcome = self._link(
                        target_path,
                        destination,
                        relative=relative,
                        canonical_path=canonical_path,
                        ignore_missing=ignore_missing,
                        link_type=link_type,
                        force=force,
                        relink=relink,
                        backup=backup,
                    )
                results[outcome] += 1
        self._log.summary(self._summary(results))
        return not results["failed"]

    def _summary(self, results: Counter[Outcome]) -> str:
        """
        Returns the line that counts the results of a link directive.
        """
        dry_run = self._context.dry_run()
        labels: list[tuple[Outcome, str]] = [
            ("created", "to create" if dry_run else "created"),
            ("updated", "to update" if dry_run else "updated"),
            ("in place", "in place"),
            ("kept", "kept with local changes"),
            ("skipped", "skipped"),
            ("failed", "failed"),
        ]
        parts = [f"{results[key]} {label}" for key, label in labels if results[key]]
        return f"link: {', '.join(parts) or 'nothing to do'}"

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

    def _link_target(self, path: str) -> str:
        """
        Returns the target of the symbolic link.
        """
        path = os.path.expanduser(path)
        path = os.readlink(path)
        if sys.platform == "win32" and path.startswith("\\\\?\\"):
            path = path[4:]
        return path

    def _create(self, path: str) -> bool:
        success = True
        parent = os.path.abspath(os.path.join(os.path.expanduser(path), os.pardir))
        if not os.path.exists(parent):
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

    def _backup_name(self, path: str) -> str:
        timestamp = datetime.now(UTC).astimezone().strftime("%Y%m%d-%H%M%S")
        return f"{path}.dotbot-backup.{timestamp}"

    def _source_in_destination(self, source: str, destination: str) -> bool:
        # Resolve the destination's parents, but keep its final entry. A link
        # at the destination can point to the source and still be safe to move.
        source_path = Path(source)
        destination_path = Path(destination)
        destination_entry = destination_path.parent.resolve() / destination_path.name
        return any(
            candidate.is_relative_to(entry)
            for candidate in (
                source_path,
                source_path.parent.resolve() / source_path.name,
                source_path.resolve(),
            )
            for entry in (destination_path, destination_entry)
        )

    def _move_to_empty_path(self, source: str, destination: str) -> None:
        if os.path.lexists(destination):
            raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), destination)
        os.rename(source, destination)

    def _install_replacement(
        self, staged: str, destination: str, backup_path: str | None
    ) -> None:
        # Replace ordinary entries in one operation where the OS permits it.
        if (
            backup_path is None
            and sys.platform != "win32"
            and not (os.path.isdir(destination) and not os.path.islink(destination))
            and not (os.path.isdir(staged) and not os.path.islink(staged))
        ):
            os.replace(staged, destination)
            return

        # Keep the original outside the staging directory so a failed restore
        # leaves it available even after the staged replacement is removed.
        holding_area = None
        if backup_path is None:
            holding_area = tempfile.mkdtemp(
                prefix=".dotbot-original-", dir=os.path.dirname(destination)
            )
            original = os.path.join(holding_area, "original")
        else:
            original = backup_path

        try:
            self._move_to_empty_path(destination, original)
        except OSError:
            if holding_area is not None:
                with contextlib.suppress(OSError):
                    os.rmdir(holding_area)
            raise
        try:
            self._move_to_empty_path(staged, destination)
        except BaseException:
            try:
                self._move_to_empty_path(original, destination)
            except OSError as error:
                self._log.error(
                    f"Could not restore {display_path(destination)}: {error_reason(error)}"
                    f". Original kept at {display_path(original)}"
                )
                holding_area = None
            finally:
                if holding_area is not None:
                    with contextlib.suppress(OSError):
                        os.rmdir(holding_area)
            raise

        if holding_area is not None:
            try:
                self._remove_path(original)
                os.rmdir(holding_area)
            except OSError as error:
                self._log.warning(
                    f"Could not remove the old contents at {display_path(original)}: {error_reason(error)}"
                )

    def _create_link(
        self, source: str, target: str, destination: str, link_type: str
    ) -> None:
        if link_type == "symlink":
            os.symlink(target, destination, target_is_directory=os.path.isdir(source))
        else:
            os.link(source, destination)

    def _link(
        self,
        target: str,
        link_name: str,
        *,
        relative: bool,
        canonical_path: bool,
        ignore_missing: bool,
        link_type: str,
        force: bool,
        relink: bool,
        backup: bool,
    ) -> Outcome:
        destination = os.path.abspath(os.path.expanduser(link_name))
        source = os.path.join(
            self._context.base_directory(canonical_path=canonical_path), target
        )
        source_exists = os.path.exists(source)
        shown_name = display_path(link_name)
        if not source_exists and not ignore_missing:
            self._log.error(
                f"Nonexistent target {shown_name} -> {display_path(target)}"
            )
            return "failed"

        link_target = (
            os.path.relpath(source, os.path.dirname(destination))
            if relative
            else source
        )
        shown_target = display_path(link_target)
        exists = os.path.lexists(destination)
        symlink = os.path.islink(destination)
        if (
            symlink
            and link_type == "symlink"
            and self._link_target(destination) == link_target
        ):
            self._log.info(f"Link exists {shown_name} -> {shown_target}")
            return "in place"
        if (
            exists
            and not symlink
            and link_type == "hardlink"
            and source_exists
            and not os.path.isdir(source)
            and os.path.samefile(destination, source)
        ):
            self._log.info(f"Link exists {shown_name} -> {shown_target}")
            return "in place"

        backup_path = (
            self._backup_name(destination)
            if exists and backup and not symlink
            else None
        )
        replace = exists and (backup_path is not None or force or (symlink and relink))
        if exists and not replace:
            if symlink and link_type == "symlink":
                terminology = "Incorrect" if os.path.exists(destination) else "Invalid"
                self._log.error(
                    f"{terminology} link {shown_name} -> {display_path(self._link_target(destination))}"
                )
            else:
                found = (
                    "symbolic link"
                    if symlink
                    else "directory"
                    if os.path.isdir(destination)
                    else "file"
                )
                expected = "hard link" if link_type == "hardlink" else "symbolic link"
                self._log.error(
                    f"{shown_name} already exists but is a {found}, not a {expected}"
                )
            return "failed"

        if link_type == "hardlink" and (not source_exists or os.path.isdir(source)):
            reason = (
                "target is a directory" if source_exists else "target does not exist"
            )
            self._log.error(f"Linking failed {shown_name} -> {shown_target}: {reason}")
            return "failed"
        if self._source_in_destination(source, destination):
            self._log.error(
                f"{shown_name} appears to be the same file as {display_path(source)} or contains it"
            )
            return "failed"

        if self._context.dry_run():
            if backup_path is not None and os.path.lexists(backup_path):
                self._log.error(f"Backup already exists at {display_path(backup_path)}")
                return "failed"
            if backup_path is not None:
                self._log.action(
                    f"Would backup {shown_name} to {display_path(backup_path)}"
                )
            elif replace:
                self._log.action(f"Would remove {shown_name}")
            self._log.action(f"Would create {link_type} {shown_name} -> {shown_target}")
            return "created"

        try:
            if replace:
                with tempfile.TemporaryDirectory(
                    prefix=".dotbot-", dir=os.path.dirname(destination)
                ) as workspace:
                    staged = os.path.join(workspace, "replacement")
                    self._create_link(source, link_target, staged, link_type)
                    self._install_replacement(staged, destination, backup_path)
            else:
                self._create_link(source, link_target, destination, link_type)
        except OSError as error:
            self._log.error(
                f"Linking failed {shown_name} -> {shown_target}: {error_reason(error)}"
            )
            return "failed"
        if backup_path is not None:
            self._log.action(
                f"Backed up file {shown_name} to {display_path(backup_path)}"
            )
        elif replace:
            self._log.action(f"Removing {shown_name}")
        self._log.action(f"Creating {link_type} {shown_name} -> {shown_target}")
        return "created"

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
    ) -> Outcome:
        """
        Copies target to link_name.

        An existing copy that is the same as the target is left as it is. A
        copy that differs is also left as it is, because it can have local
        changes, unless force or backup is set: then the copy is updated (after
        a backup moves the old copy away). A directory is copied file by file,
        and files that are only in the copy are kept. A symlink at link_name is
        replaced only if relink or force is set, and so is a file where the
        target is a directory (or the other way around).

        Returns the result: created, updated, in place, kept (a copy that
        differs), skipped (a missing target with ignore-missing), or failed.
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
                return "skipped"
            self._log.error(
                f"Nonexistent target {display_path(link_name)} -> {display_path(source)}"
            )
            return "failed"

        exists = os.path.lexists(destination)
        symlink = os.path.islink(destination)
        if symlink and not (relink or force):
            self._log.error(
                f"{display_path(link_name)} already exists but is a symbolic link, not a copy"
            )
            return "failed"
        source_is_directory = os.path.isdir(source)
        other_type = (
            exists and not symlink and source_is_directory != os.path.isdir(destination)
        )
        if other_type and not (force or backup):
            expected, found = (
                ("directory", "file") if source_is_directory else ("file", "directory")
            )
            self._log.error(
                f"{display_path(link_name)} already exists but is a {found}, not a {expected}"
            )
            return "failed"
        if exists and not (symlink or other_type):
            try:
                differs = self._differs(source, destination)
            except OSError as e:
                self._log.error(
                    f"Failed to compare {display_path(link_name)} with {display_path(source)}: {error_reason(e)}"
                )
                return "failed"
            if not differs:
                self._log.info(
                    f"Copy exists {display_path(link_name)} -> {display_path(source)}"
                )
                return "in place"
            if not (force or backup):
                self._log.info(
                    f"Copy {display_path(link_name)} differs from {display_path(source)}, keeping it"
                )
                return "kept"

        backup_path = (
            self._backup_name(destination)
            if exists and backup and not symlink
            else None
        )
        replace = symlink or other_type or backup_path is not None
        destination_entry = Path(destination).parent.resolve() / Path(destination).name
        if self._source_in_destination(source, destination) or (
            source_is_directory
            and destination_entry.is_relative_to(Path(source).resolve())
        ):
            self._log.error(
                f"Cannot copy {display_path(source)} to {display_path(link_name)}: the paths overlap"
            )
            return "failed"

        update = exists and not replace
        verb = "update" if update else "create"
        if self._context.dry_run():
            if backup_path is not None and os.path.lexists(backup_path):
                self._log.error(f"Backup already exists at {display_path(backup_path)}")
                return "failed"
            if backup_path is not None:
                self._log.action(
                    f"Would backup {display_path(link_name)} to {display_path(backup_path)}"
                )
            elif replace:
                self._log.action(f"Would remove {display_path(link_name)}")
            self._log.action(
                f"Would {verb} copy {display_path(link_name)} -> {display_path(source)}"
            )
            return "updated" if update else "created"
        try:
            self._write_copy(
                source, destination, replace=replace, backup_path=backup_path
            )
        except OSError as e:
            self._log.error(
                f"Copying failed {display_path(link_name)} -> {display_path(source)}: {error_reason(e)}"
            )
            return "failed"
        if backup_path is not None:
            self._log.action(
                f"Backed up file {display_path(link_name)} to {display_path(backup_path)}"
            )
        elif replace:
            self._log.action(f"Removing {display_path(link_name)}")
        self._log.action(
            f"{'Updating' if update else 'Creating'} copy {display_path(link_name)} -> {display_path(source)}"
        )
        return "updated" if update else "created"

    def _write_copy(
        self,
        source: str,
        destination: str,
        *,
        replace: bool,
        backup_path: str | None = None,
    ) -> None:
        copy = self._copy_directory if os.path.isdir(source) else self._copy_file
        if not replace:
            copy(source, destination)
            return
        with tempfile.TemporaryDirectory(
            prefix=".dotbot-", dir=os.path.dirname(destination)
        ) as workspace:
            staged = os.path.join(workspace, "replacement")
            copy(source, staged)
            self._install_replacement(staged, destination, backup_path)

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
            if os.path.lexists(destination):
                self._install_replacement(temporary, destination, None)
            else:
                self._move_to_empty_path(temporary, destination)
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
            if os.path.lexists(destination):
                self._write_copy(source, destination, replace=True)
                return
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
        if os.path.islink(destination):
            return True
        if not os.path.isdir(source):
            return not os.path.isfile(destination) or not filecmp.cmp(
                source, destination, shallow=False
            )
        if not os.path.isdir(destination):
            return True
        return any(
            self._differs(os.path.join(source, name), os.path.join(destination, name))
            for name in os.listdir(source)
        )

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

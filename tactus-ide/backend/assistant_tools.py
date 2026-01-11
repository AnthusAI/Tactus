"""
File management tools for the AI coding assistant.

Provides sandboxed file operations that are restricted to the workspace directory.
All paths are validated to prevent directory traversal attacks.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class FileToolsError(Exception):
    """Base exception for file tool errors."""

    pass


class PathSecurityError(FileToolsError):
    """Raised when a path tries to escape the workspace."""

    pass


def validate_path(workspace_root: str, path: str) -> Path:
    """
    Validate that a path is within the workspace.

    Args:
        workspace_root: Absolute path to workspace root
        path: Relative or absolute path to validate

    Returns:
        Resolved absolute Path object

    Raises:
        PathSecurityError: If path escapes workspace
    """
    workspace = Path(workspace_root).resolve()

    # Handle both relative and absolute paths
    if os.path.isabs(path):
        target = Path(path).resolve()
    else:
        target = (workspace / path).resolve()

    # Check if target is within workspace
    try:
        target.relative_to(workspace)
    except ValueError:
        raise PathSecurityError(f"Path '{path}' is outside workspace '{workspace_root}'")

    return target


def read_file(workspace_root: str, path: str) -> str:
    """
    Read contents of a file.

    Args:
        workspace_root: Workspace root directory
        path: Path to file (relative to workspace)

    Returns:
        File contents as string

    Raises:
        PathSecurityError: If path escapes workspace
        FileToolsError: If file cannot be read
    """
    try:
        target = validate_path(workspace_root, path)

        if not target.exists():
            raise FileToolsError(f"File not found: {path}")

        if not target.is_file():
            raise FileToolsError(f"Not a file: {path}")

        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        logger.info(f"Read file: {path} ({len(content)} bytes)")
        return content

    except PathSecurityError:
        raise
    except Exception as e:
        raise FileToolsError(f"Failed to read file '{path}': {str(e)}")


def list_files(workspace_root: str, path: str = ".") -> List[Dict[str, Any]]:
    """
    List files and directories in a path.

    Args:
        workspace_root: Workspace root directory
        path: Path to directory (relative to workspace, default ".")

    Returns:
        List of dicts with: name, type (file/directory), size

    Raises:
        PathSecurityError: If path escapes workspace
        FileToolsError: If directory cannot be listed
    """
    try:
        target = validate_path(workspace_root, path)

        if not target.exists():
            raise FileToolsError(f"Directory not found: {path}")

        if not target.is_dir():
            raise FileToolsError(f"Not a directory: {path}")

        entries = []
        for entry in sorted(target.iterdir()):
            try:
                stat = entry.stat()
                entries.append(
                    {
                        "name": entry.name,
                        "type": "directory" if entry.is_dir() else "file",
                        "size": stat.st_size if entry.is_file() else None,
                        "path": str(entry.relative_to(workspace_root)),
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to stat {entry}: {e}")
                continue

        logger.info(f"Listed directory: {path} ({len(entries)} entries)")
        return entries

    except PathSecurityError:
        raise
    except Exception as e:
        raise FileToolsError(f"Failed to list directory '{path}': {str(e)}")


def search_files(workspace_root: str, pattern: str, path: str = ".") -> List[str]:
    """
    Search for files matching a pattern.

    Args:
        workspace_root: Workspace root directory
        pattern: Glob pattern (e.g., "*.tac", "**/*.py")
        path: Starting directory (relative to workspace, default ".")

    Returns:
        List of matching file paths (relative to workspace)

    Raises:
        PathSecurityError: If path escapes workspace
        FileToolsError: If search fails
    """
    try:
        target = validate_path(workspace_root, path)

        if not target.exists():
            raise FileToolsError(f"Directory not found: {path}")

        if not target.is_dir():
            raise FileToolsError(f"Not a directory: {path}")

        matches = []
        for match in target.glob(pattern):
            if match.is_file():
                rel_path = str(match.relative_to(workspace_root))
                matches.append(rel_path)

        logger.info(f"Search '{pattern}' in {path}: {len(matches)} matches")
        return sorted(matches)

    except PathSecurityError:
        raise
    except Exception as e:
        raise FileToolsError(f"Failed to search '{pattern}' in '{path}': {str(e)}")


def write_file(workspace_root: str, path: str, content: str) -> Dict[str, Any]:
    """
    Write content to a file (creates if doesn't exist).

    Args:
        workspace_root: Workspace root directory
        path: Path to file (relative to workspace)
        content: Content to write

    Returns:
        Dict with: path, size, created (bool)

    Raises:
        PathSecurityError: If path escapes workspace
        FileToolsError: If file cannot be written
    """
    try:
        target = validate_path(workspace_root, path)

        # Check if file already exists
        existed = target.exists()

        # Create parent directories if needed
        target.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        size = target.stat().st_size

        action = "Updated" if existed else "Created"
        logger.info(f"{action} file: {path} ({size} bytes)")

        return {"path": path, "size": size, "created": not existed}

    except PathSecurityError:
        raise
    except Exception as e:
        raise FileToolsError(f"Failed to write file '{path}': {str(e)}")


def edit_file(workspace_root: str, path: str, old_string: str, new_string: str) -> Dict[str, Any]:
    """
    Edit a file using search/replace.

    Args:
        workspace_root: Workspace root directory
        path: Path to file (relative to workspace)
        old_string: String to search for
        new_string: String to replace with

    Returns:
        Dict with: path, replacements (count)

    Raises:
        PathSecurityError: If path escapes workspace
        FileToolsError: If file cannot be edited
    """
    try:
        target = validate_path(workspace_root, path)

        if not target.exists():
            raise FileToolsError(f"File not found: {path}")

        if not target.is_file():
            raise FileToolsError(f"Not a file: {path}")

        # Read current content
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if old_string exists
        if old_string not in content:
            raise FileToolsError(f"String not found in file: {old_string[:50]}...")

        # Replace
        new_content = content.replace(old_string, new_string)
        count = content.count(old_string)

        # Write back
        with open(target, "w", encoding="utf-8") as f:
            f.write(new_content)

        logger.info(f"Edited file: {path} ({count} replacements)")

        return {"path": path, "replacements": count}

    except PathSecurityError:
        raise
    except Exception as e:
        raise FileToolsError(f"Failed to edit file '{path}': {str(e)}")


def delete_file(workspace_root: str, path: str) -> Dict[str, Any]:
    """
    Delete a file.

    Args:
        workspace_root: Workspace root directory
        path: Path to file (relative to workspace)

    Returns:
        Dict with: path, deleted (bool)

    Raises:
        PathSecurityError: If path escapes workspace
        FileToolsError: If file cannot be deleted
    """
    try:
        target = validate_path(workspace_root, path)

        if not target.exists():
            raise FileToolsError(f"File not found: {path}")

        if target.is_dir():
            raise FileToolsError(f"Cannot delete directory (use delete_directory): {path}")

        target.unlink()

        logger.info(f"Deleted file: {path}")

        return {"path": path, "deleted": True}

    except PathSecurityError:
        raise
    except Exception as e:
        raise FileToolsError(f"Failed to delete file '{path}': {str(e)}")


def move_file(workspace_root: str, from_path: str, to_path: str) -> Dict[str, Any]:
    """
    Move or rename a file.

    Args:
        workspace_root: Workspace root directory
        from_path: Source path (relative to workspace)
        to_path: Destination path (relative to workspace)

    Returns:
        Dict with: from_path, to_path, moved (bool)

    Raises:
        PathSecurityError: If either path escapes workspace
        FileToolsError: If file cannot be moved
    """
    try:
        source = validate_path(workspace_root, from_path)
        dest = validate_path(workspace_root, to_path)

        if not source.exists():
            raise FileToolsError(f"Source file not found: {from_path}")

        if dest.exists():
            raise FileToolsError(f"Destination already exists: {to_path}")

        # Create parent directories if needed
        dest.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(source), str(dest))

        logger.info(f"Moved file: {from_path} -> {to_path}")

        return {"from_path": from_path, "to_path": to_path, "moved": True}

    except PathSecurityError:
        raise
    except Exception as e:
        raise FileToolsError(f"Failed to move file '{from_path}' to '{to_path}': {str(e)}")


def copy_file(workspace_root: str, from_path: str, to_path: str) -> Dict[str, Any]:
    """
    Copy a file.

    Args:
        workspace_root: Workspace root directory
        from_path: Source path (relative to workspace)
        to_path: Destination path (relative to workspace)

    Returns:
        Dict with: from_path, to_path, copied (bool)

    Raises:
        PathSecurityError: If either path escapes workspace
        FileToolsError: If file cannot be copied
    """
    try:
        source = validate_path(workspace_root, from_path)
        dest = validate_path(workspace_root, to_path)

        if not source.exists():
            raise FileToolsError(f"Source file not found: {from_path}")

        if not source.is_file():
            raise FileToolsError(f"Source is not a file: {from_path}")

        if dest.exists():
            raise FileToolsError(f"Destination already exists: {to_path}")

        # Create parent directories if needed
        dest.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(str(source), str(dest))

        logger.info(f"Copied file: {from_path} -> {to_path}")

        return {"from_path": from_path, "to_path": to_path, "copied": True}

    except PathSecurityError:
        raise
    except Exception as e:
        raise FileToolsError(f"Failed to copy file '{from_path}' to '{to_path}': {str(e)}")

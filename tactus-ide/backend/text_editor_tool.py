"""
Text editor tool following Claude's native text_editor_20250728 pattern.

This implements the view command for reading files and listing directories,
with line numbers and proper formatting as Claude 4.x models expect.
"""

from typing import List, Optional

from assistant_tools import validate_path, FileToolsError, PathSecurityError


def view_file(workspace_root: str, path: str, view_range: Optional[List[int]] = None) -> str:
    """
    View file contents with line numbers (1-indexed).

    Args:
        workspace_root: Absolute path to workspace root
        path: Relative path to file
        view_range: Optional [start_line, end_line] where:
                   - Lines are 1-indexed
                   - Use -1 for end_line to read to end of file

    Returns:
        Formatted string with line numbers: "1: line content\\n2: line content\\n..."

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

        # Read file
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Handle view_range
        if view_range:
            start, end = view_range
            # Convert to 0-indexed
            start_idx = start - 1
            if end == -1:
                end_idx = len(lines)
            else:
                end_idx = end

            # Validate range
            if start_idx < 0:
                raise FileToolsError(f"Invalid start line: {start} (must be >= 1)")
            if start_idx >= len(lines):
                raise FileToolsError(f"Start line {start} exceeds file length ({len(lines)} lines)")

            lines = lines[start_idx:end_idx]
            start_num = start
        else:
            start_num = 1

        # Format with line numbers
        formatted_lines = []
        for i, line in enumerate(lines, start=start_num):
            # Remove trailing newline but preserve other whitespace
            line_content = line.rstrip("\n\r")
            formatted_lines.append(f"{i}: {line_content}")

        return "\n".join(formatted_lines)

    except (PathSecurityError, FileToolsError):
        raise
    except Exception as e:
        raise FileToolsError(f"Failed to read file '{path}': {str(e)}")


def view_directory(workspace_root: str, path: str) -> str:
    """
    List directory contents with [DIR]/[FILE] markers.

    Args:
        workspace_root: Absolute path to workspace root
        path: Relative path to directory

    Returns:
        Formatted string showing directories and files:
        "[DIR]  subdir/\\n[FILE] file.txt (1234 bytes)\\n..."

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

        # List entries
        entries = []
        for entry in sorted(target.iterdir()):
            try:
                if entry.is_dir():
                    entries.append(f"[DIR]  {entry.name}/")
                else:
                    stat = entry.stat()
                    size = stat.st_size
                    entries.append(f"[FILE] {entry.name} ({size} bytes)")
            except Exception as e:
                # Skip entries we can't access
                entries.append(f"[????] {entry.name} (error: {e})")

        if not entries:
            return f"Directory '{path}' is empty"

        return "\n".join(entries)

    except (PathSecurityError, FileToolsError):
        raise
    except Exception as e:
        raise FileToolsError(f"Failed to list directory '{path}': {str(e)}")


def str_replace_based_edit_tool(
    workspace_root: str, command: str, path: str, view_range: Optional[List[int]] = None
) -> str:
    """
    Main text editor tool function following Claude's native pattern.

    This is the single entry point for all text editor operations.
    Currently supports only the 'view' command (read-only).

    Args:
        workspace_root: Absolute path to workspace root
        command: Command to execute ('view' is currently supported)
        path: Relative path to file or directory
        view_range: Optional [start_line, end_line] for viewing specific lines

    Returns:
        Result string from the command

    Raises:
        PathSecurityError: If path escapes workspace
        FileToolsError: If operation fails
    """
    try:
        if command == "view":
            target = validate_path(workspace_root, path)

            if target.is_file():
                return view_file(workspace_root, path, view_range)
            elif target.is_dir():
                if view_range:
                    return "Error: view_range parameter not supported for directories"
                return view_directory(workspace_root, path)
            else:
                raise FileToolsError(f"Path is neither file nor directory: {path}")
        else:
            return f"Error: Command '{command}' not supported (read-only mode)"

    except PathSecurityError as e:
        return f"Error: {str(e)}"
    except FileToolsError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: Unexpected error: {str(e)}"

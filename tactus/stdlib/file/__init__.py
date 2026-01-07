"""Standard library file operations tool for Tactus.

Provides file reading and writing utilities that agents can use.
"""

import json
from pathlib import Path
from typing import Optional, Literal, Union


def read_file(path: str, encoding: str = "utf-8", mode: Literal["text", "json"] = "text") -> dict:
    """Read a file from the filesystem.

    Args:
        path: Path to the file to read
        encoding: Text encoding (default: utf-8)
        mode: Read mode - "text" for plain text, "json" to parse as JSON

    Returns:
        Dict with status and content

    Examples:
        >>> read_file("config.txt")
        {'status': 'success', 'content': 'file contents here', 'path': 'config.txt'}

        >>> read_file("data.json", mode="json")
        {'status': 'success', 'content': {'key': 'value'}, 'path': 'data.json'}
    """
    try:
        file_path = Path(path)

        if not file_path.exists():
            return {"status": "error", "error": f"File not found: {path}", "path": path}

        if not file_path.is_file():
            return {"status": "error", "error": f"Not a file: {path}", "path": path}

        with open(file_path, "r", encoding=encoding) as f:
            content = f.read()

        if mode == "json":
            try:
                content = json.loads(content)
            except json.JSONDecodeError as e:
                return {"status": "error", "error": f"Invalid JSON: {str(e)}", "path": path}

        return {
            "status": "success",
            "content": content,
            "path": path,
            "size": file_path.stat().st_size,
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "path": path}


def write_file(
    path: str,
    content: Union[str, dict, list],
    encoding: str = "utf-8",
    mode: Literal["text", "json"] = "text",
    create_dirs: bool = True,
) -> dict:
    """Write content to a file.

    Args:
        path: Path to the file to write
        content: Content to write (string for text mode, dict/list for json mode)
        encoding: Text encoding (default: utf-8)
        mode: Write mode - "text" for plain text, "json" to serialize as JSON
        create_dirs: Whether to create parent directories if they don't exist

    Returns:
        Dict with status and file info

    Examples:
        >>> write_file("output.txt", "Hello, World!")
        {'status': 'success', 'path': 'output.txt', 'bytes_written': 13}

        >>> write_file("data.json", {"key": "value"}, mode="json")
        {'status': 'success', 'path': 'data.json', 'bytes_written': 16}
    """
    try:
        file_path = Path(path)

        # Create parent directories if requested
        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        # Prepare content based on mode
        if mode == "json":
            if not isinstance(content, (dict, list)):
                return {
                    "status": "error",
                    "error": "Content must be dict or list for JSON mode",
                    "path": path,
                }
            write_content = json.dumps(content, indent=2)
        else:
            if not isinstance(content, str):
                write_content = str(content)
            else:
                write_content = content

        # Write the file
        with open(file_path, "w", encoding=encoding) as f:
            bytes_written = f.write(write_content)

        return {"status": "success", "path": path, "bytes_written": bytes_written}

    except Exception as e:
        return {"status": "error", "error": str(e), "path": path}


def list_files(
    directory: str = ".", pattern: Optional[str] = None, recursive: bool = False
) -> dict:
    """List files in a directory.

    Args:
        directory: Directory path (default: current directory)
        pattern: Optional glob pattern to filter files (e.g., "*.txt")
        recursive: Whether to search recursively in subdirectories

    Returns:
        Dict with status and list of files

    Examples:
        >>> list_files()
        {'status': 'success', 'files': ['file1.txt', 'file2.py'], 'count': 2}

        >>> list_files("src", pattern="*.py", recursive=True)
        {'status': 'success', 'files': ['src/main.py', 'src/lib/utils.py'], 'count': 2}
    """
    try:
        dir_path = Path(directory)

        if not dir_path.exists():
            return {
                "status": "error",
                "error": f"Directory not found: {directory}",
                "directory": directory,
            }

        if not dir_path.is_dir():
            return {
                "status": "error",
                "error": f"Not a directory: {directory}",
                "directory": directory,
            }

        # Get files based on pattern and recursion
        if pattern:
            if recursive:
                files = list(dir_path.rglob(pattern))
            else:
                files = list(dir_path.glob(pattern))
        else:
            if recursive:
                files = list(dir_path.rglob("*"))
            else:
                files = list(dir_path.glob("*"))

        # Filter to only files (not directories)
        file_paths = [str(f.relative_to(dir_path)) for f in files if f.is_file()]

        return {
            "status": "success",
            "files": sorted(file_paths),
            "count": len(file_paths),
            "directory": directory,
        }

    except Exception as e:
        return {"status": "error", "error": str(e), "directory": directory}


def file_exists(path: str) -> dict:
    """Check if a file exists.

    Args:
        path: Path to check

    Returns:
        Dict with status and existence info

    Examples:
        >>> file_exists("config.txt")
        {'status': 'success', 'exists': True, 'path': 'config.txt', 'is_file': True}
    """
    try:
        file_path = Path(path)
        exists = file_path.exists()

        result = {"status": "success", "exists": exists, "path": path}

        if exists:
            result["is_file"] = file_path.is_file()
            result["is_dir"] = file_path.is_dir()
            if file_path.is_file():
                result["size"] = file_path.stat().st_size

        return result

    except Exception as e:
        return {"status": "error", "error": str(e), "path": path}


# Export all file operations
__all__ = ["read_file", "write_file", "list_files", "file_exists"]


# For simpler import, provide a default "file" tool that combines operations
def file(operation: Literal["read", "write", "list", "exists"], **kwargs) -> dict:
    """Unified file operations tool.

    Args:
        operation: The file operation to perform
        **kwargs: Arguments for the specific operation

    Returns:
        Result from the operation
    """
    operations = {"read": read_file, "write": write_file, "list": list_files, "exists": file_exists}

    if operation not in operations:
        return {"status": "error", "error": f"Unknown operation: {operation}"}

    return operations[operation](**kwargs)

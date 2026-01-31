"""
File Primitive - File I/O operations for workflows.

Provides:
- File.read(path) - Read file contents
- File.write(path, content) - Write content to file
- File.exists(path) - Check if file exists
- File.size(path) - Get file size in bytes
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FilePrimitive:
    """
    Handles file operations for procedures.

    Enables workflows to:
    - Read file contents
    - Write data to files
    - Check file existence
    - Get file metadata

    Note: File operations are non-deterministic (files can change between executions).
    Wrap in Step.checkpoint() for durability.
    """

    def __init__(self, base_path: Optional[str] = None, execution_context=None):
        """
        Initialize File primitive.

        Args:
            base_path: Optional base directory for relative paths (defaults to cwd)
            execution_context: Optional ExecutionContext for determinism checking
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.execution_context = execution_context
        logger.debug("FilePrimitive initialized with base_path: %s", self.base_path)

    def _check_determinism(self, operation: str) -> None:
        """Warn if file operation called outside checkpoint."""
        if self.execution_context and not getattr(
            self.execution_context, "_inside_checkpoint", False
        ):
            import warnings

            warning_banner = "=" * 70
            warnings.warn(
                "\n"
                f"{warning_banner}\n"
                f"DETERMINISM WARNING: File.{operation}() called outside checkpoint\n"
                f"{warning_banner}\n\n"
                "File operations are non-deterministic - "
                "file contents can change between executions.\n\n"
                "To fix, wrap in Step.checkpoint():\n\n"
                "  state.data = Step.checkpoint(function()\n"
                f"    return File.{operation}(...)\n"
                "  end)\n\n"
                "Why: Files can be modified, deleted, or created "
                "between procedure executions,\n"
                "causing different behavior on replay.\n"
                f"\n{warning_banner}\n",
                UserWarning,
                stacklevel=3,
            )

    def read(self, path: str) -> str:
        """
        Read file contents as string.

        Args:
            path: File path to read (absolute or relative to base_path)

        Returns:
            File contents as string

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read

        Example (Lua):
            local config = File.read("config.json")
            Log.info("Config loaded", {length = #config})
        """
        self._check_determinism("read")
        file_path = self._resolve_path(path)

        try:
            logger.debug("Reading file: %s", file_path)
            with open(file_path, "r", encoding="utf-8") as file_handle:
                content = file_handle.read()
            logger.info("Read %s bytes from %s", len(content), file_path)
            return content

        except FileNotFoundError:
            error_message = f"File not found: {file_path}"
            logger.error(error_message)
            raise FileNotFoundError(error_message)

        except Exception as error:
            error_message = f"Failed to read file {file_path}: {error}"
            logger.error(error_message)
            raise IOError(error_message)

    def write(self, path: str, content: str) -> bool:
        """
        Write content to file.

        Args:
            path: File path to write (absolute or relative to base_path)
            content: Content to write

        Returns:
            True if successful

        Raises:
            IOError: If file cannot be written

        Example (Lua):
            local data = Json.encode({status = "complete"})
            File.write("output.json", data)
            Log.info("Data written")
        """
        self._check_determinism("write")
        file_path = self._resolve_path(path)

        try:
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            logger.debug("Writing to file: %s", file_path)
            with open(file_path, "w", encoding="utf-8") as file_handle:
                file_handle.write(content)

            logger.info("Wrote %s bytes to %s", len(content), file_path)
            return True

        except Exception as error:
            error_message = f"Failed to write file {file_path}: {error}"
            logger.error(error_message)
            raise IOError(error_message)

    def exists(self, path: str) -> bool:
        """
        Check if file exists.

        Args:
            path: File path to check (absolute or relative to base_path)

        Returns:
            True if file exists, False otherwise

        Example (Lua):
            if File.exists("cache.json") then
                local data = File.read("cache.json")
                Log.info("Using cached data")
            else
                Log.info("No cache found")
            end
        """
        self._check_determinism("exists")
        file_path = self._resolve_path(path)
        file_exists = file_path.exists() and file_path.is_file()
        logger.debug("File exists check for %s: %s", file_path, file_exists)
        return file_exists

    def size(self, path: str) -> int:
        """
        Get file size in bytes.

        Args:
            path: File path to check (absolute or relative to base_path)

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist

        Example (Lua):
            local size = File.size("data.csv")
            Log.info("File size", {bytes = size, kb = size / 1024})
        """
        self._check_determinism("size")
        file_path = self._resolve_path(path)

        if not file_path.exists():
            error_message = f"File not found: {file_path}"
            logger.error(error_message)
            raise FileNotFoundError(error_message)

        file_size_bytes = file_path.stat().st_size
        logger.debug("File size for %s: %s bytes", file_path, file_size_bytes)
        return file_size_bytes

    def _resolve_path(self, path: str) -> Path:
        """
        Resolve file path relative to base_path with security validation.

        Args:
            path: File path to resolve (must be relative)

        Returns:
            Resolved Path object

        Raises:
            ValueError: If absolute path or path traversal detected
        """
        relative_path = Path(path)

        # Security: Never allow absolute paths
        if relative_path.is_absolute():
            raise ValueError(f"Absolute paths not allowed: {path}")

        # Resolve relative to base_path
        resolved_path = (self.base_path / relative_path).resolve()

        # Security: Verify resolved path is under base_path
        try:
            resolved_path.relative_to(self.base_path)
        except ValueError:
            raise ValueError(f"Path traversal detected: {path} resolves outside base directory")

        return resolved_path

    def __repr__(self) -> str:
        return f"FilePrimitive(base_path={self.base_path})"

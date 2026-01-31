"""
Docker management utilities for sandbox execution.

Handles Docker availability detection, image building, and version management.
"""

import hashlib
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default image name for local sandbox
DEFAULT_IMAGE_NAME = "tactus-sandbox"
DEFAULT_IMAGE_TAG = "local"


def resolve_dockerfile_path(tactus_root: Path) -> tuple[Path, str]:
    """
    Choose the appropriate Dockerfile for the sandbox build.

    Returns:
        Tuple of (dockerfile_path, build_mode) where build_mode is "source" or "pypi".
    """
    docker_dir = tactus_root / "tactus" / "docker"
    source_dockerfile = docker_dir / "Dockerfile"
    pypi_dockerfile = docker_dir / "Dockerfile.pypi"
    has_source_tree = (tactus_root / "pyproject.toml").exists() and (
        tactus_root / "README.md"
    ).exists()

    if has_source_tree or not pypi_dockerfile.exists():
        return source_dockerfile, "source"

    return pypi_dockerfile, "pypi"


def calculate_source_hash(tactus_root: Path) -> str:
    """
    Calculate hash of Tactus source files for change detection.

    This enables fast, automatic rebuilds when code changes without
    requiring manual version bumps or rebuild commands.

    Args:
        tactus_root: Root directory of the Tactus package

    Returns:
        Short hash (16 chars) representing the current state of source code
    """
    # Key paths that affect sandbox behavior
    paths_to_hash = [
        tactus_root / "tactus" / "dspy",
        tactus_root / "tactus" / "adapters",
        tactus_root / "tactus" / "broker",  # Broker client used by sandbox
        tactus_root / "tactus" / "core",
        tactus_root / "tactus" / "primitives",
        tactus_root / "tactus" / "sandbox",
        tactus_root / "tactus" / "stdlib",
        tactus_root / "tactus" / "docker",
        tactus_root / "pyproject.toml",  # Dependencies affect sandbox
    ]

    hasher = hashlib.sha256()

    for path in sorted(paths_to_hash):
        if not path.exists():
            continue

        if path.is_file():
            # Hash file contents
            hasher.update(path.read_bytes())
        elif path.is_dir():
            # Hash directory files (recursively), skipping caches.
            for file in sorted(path.rglob("*")):
                if not file.is_file():
                    continue
                if "__pycache__" in file.parts:
                    continue
                if file.suffix == ".pyc":
                    continue
                if file.name == ".DS_Store":
                    continue

                # Hash relative path + contents for reproducibility
                rel_path = str(file.relative_to(tactus_root))
                hasher.update(rel_path.encode())
                hasher.update(file.read_bytes())

    # Return short hash (16 chars is plenty for collision avoidance)
    return hasher.hexdigest()[:16]


def is_docker_available() -> tuple[bool, str]:
    """
    Check if Docker is available and running.

    Returns:
        Tuple of (available, reason) where:
        - available: True if Docker is ready to use
        - reason: Empty string if available, otherwise explanation of why not
    """
    # Check if docker CLI exists
    docker_path = shutil.which("docker")
    if not docker_path:
        return False, "Docker CLI not found in PATH"

    try:
        # Check if Docker daemon is running
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            # Parse common error messages
            stderr = result.stderr.lower()
            if "cannot connect" in stderr or "connection refused" in stderr:
                return False, "Docker daemon not running"
            if "permission denied" in stderr:
                return (
                    False,
                    "Permission denied accessing Docker (try: sudo usermod -aG docker $USER)",
                )
            return False, f"Docker error: {result.stderr.strip()}"

        return True, ""

    except subprocess.TimeoutExpired:
        return False, "Docker daemon not responding (timeout after 10s)"
    except FileNotFoundError:
        return False, "Docker CLI not found"
    except Exception as error:
        return False, f"Docker check failed: {error}"


class DockerManager:
    """
    Manages Docker images for sandbox execution.

    Handles image building, version checking, and cleanup.
    """

    def __init__(
        self,
        image_name: str = DEFAULT_IMAGE_NAME,
        image_tag: str = DEFAULT_IMAGE_TAG,
    ):
        """
        Initialize Docker manager.

        Args:
            image_name: Base name for Docker images
            image_tag: Tag for the image (e.g., 'local', 'v1.0.0')
        """
        self.image_name = image_name
        self.image_tag = image_tag
        self.full_image_name = f"{image_name}:{image_tag}"

    def image_exists(self) -> bool:
        """Check if the sandbox image exists locally."""
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", self.full_image_name],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, Exception):
            return False

    def get_image_version(self) -> Optional[str]:
        """
        Get the Tactus version label from the existing image.

        Returns:
            Version string if found, None otherwise.
        """
        try:
            result = subprocess.run(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    '{{index .Config.Labels "tactus.version"}}',
                    self.full_image_name,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None
        except Exception:
            return None

    def get_image_source_hash(self) -> Optional[str]:
        """
        Get the source hash label from the existing image.

        Returns:
            Source hash string if found, None otherwise.
        """
        try:
            result = subprocess.run(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    '{{index .Config.Labels "tactus.source_hash"}}',
                    self.full_image_name,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None
        except Exception:
            return None

    def needs_rebuild(self, current_version: str, current_hash: Optional[str] = None) -> bool:
        """
        Check if the image needs to be rebuilt.

        Checks both version and source hash (if provided) to determine
        if a rebuild is necessary. This enables automatic rebuilds when
        code changes without requiring manual version bumps.

        Args:
            current_version: Current Tactus version.
            current_hash: Optional source hash of current code. If provided,
                         will trigger rebuild when hash doesn't match.

        Returns:
            True if image should be rebuilt.
        """
        if not self.image_exists():
            return True

        # Check version mismatch
        image_version = self.get_image_version()
        if image_version is None:
            return True

        if image_version != current_version:
            return True

        # Check source hash mismatch (if hash checking is enabled)
        if current_hash is not None:
            image_hash = self.get_image_source_hash()
            if image_hash is None:
                # Old image without hash label - rebuild to add it
                logger.debug("Image missing source hash label, rebuild needed")
                return True

            if image_hash != current_hash:
                logger.debug("Source hash mismatch: %s != %s", image_hash, current_hash)
                return True

        return False

    def build_image(
        self,
        dockerfile_path: Path,
        context_path: Path,
        version: str,
        source_hash: Optional[str] = None,
        verbose: bool = False,
    ) -> tuple[bool, str]:
        """
        Build the sandbox Docker image.

        Args:
            dockerfile_path: Path to the Dockerfile
            context_path: Build context path (usually the Tactus package root)
            version: Tactus version to label the image with
            source_hash: Optional source hash to label the image with for change detection
            verbose: If True, stream build output

        Returns:
            Tuple of (success, message)
        """
        if not dockerfile_path.exists():
            return False, f"Dockerfile not found: {dockerfile_path}"

        if not context_path.exists():
            return False, f"Build context not found: {context_path}"

        logger.info("Building sandbox image: %s", self.full_image_name)

        cmd = [
            "docker",
            "build",
            "-t",
            self.full_image_name,
            "-f",
            str(dockerfile_path),
            "--build-arg",
            f"TACTUS_VERSION={version}",
            "--label",
            f"tactus.version={version}",
        ]

        # Add source hash label if provided
        if source_hash:
            cmd.extend(["--label", f"tactus.source_hash={source_hash}"])

        cmd.append(str(context_path))

        try:
            if verbose:
                # Stream output in real-time
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                output_lines = []
                for line in iter(process.stdout.readline, ""):
                    if line:
                        output_lines.append(line.rstrip())
                        logger.info("%s", line.rstrip())
                process.wait()
                returncode = process.returncode
                output = "\n".join(output_lines)
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minute timeout for builds
                )
                returncode = result.returncode
                output = result.stderr if result.returncode != 0 else result.stdout

            if returncode == 0:
                logger.info("Successfully built: %s", self.full_image_name)
                return True, f"Successfully built {self.full_image_name}"
            else:
                return False, f"Build failed: {output}"

        except subprocess.TimeoutExpired:
            return False, "Build timed out after 10 minutes"
        except Exception as error:
            return False, f"Build failed: {error}"

    def ensure_image_exists(
        self,
        dockerfile_path: Path,
        context_path: Path,
        version: str,
        force_rebuild: bool = False,
    ) -> tuple[bool, str]:
        """
        Ensure the sandbox image exists, building if necessary.

        Args:
            dockerfile_path: Path to the Dockerfile
            context_path: Build context path
            version: Current Tactus version
            force_rebuild: If True, rebuild even if image exists

        Returns:
            Tuple of (success, message)
        """
        if force_rebuild or self.needs_rebuild(version):
            return self.build_image(dockerfile_path, context_path, version)

        return True, f"Image {self.full_image_name} is up to date"

    def remove_image(self) -> tuple[bool, str]:
        """
        Remove the sandbox image.

        Returns:
            Tuple of (success, message)
        """
        if not self.image_exists():
            return True, f"Image {self.full_image_name} does not exist"

        try:
            result = subprocess.run(
                ["docker", "rmi", self.full_image_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return True, f"Removed {self.full_image_name}"
            else:
                return False, f"Failed to remove image: {result.stderr}"
        except Exception as error:
            return False, f"Failed to remove image: {error}"

    def cleanup_old_images(self, keep_tags: Optional[list[str]] = None) -> int:
        """
        Remove old sandbox images, keeping specified tags.

        Args:
            keep_tags: List of tags to keep. Defaults to ['local'].

        Returns:
            Number of images removed.
        """
        if keep_tags is None:
            keep_tags = [DEFAULT_IMAGE_TAG]

        try:
            # List all images with our base name
            result = subprocess.run(
                [
                    "docker",
                    "images",
                    "--format",
                    "{{.Repository}}:{{.Tag}}",
                    self.image_name,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return 0

            removed = 0
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                # Parse image:tag
                if ":" in line:
                    _, tag = line.rsplit(":", 1)
                    if tag not in keep_tags:
                        rm_result = subprocess.run(
                            ["docker", "rmi", line],
                            capture_output=True,
                            timeout=30,
                        )
                        if rm_result.returncode == 0:
                            removed += 1
                            logger.info("Removed old image: %s", line)

            return removed

        except Exception as error:
            logger.warning("Failed to cleanup old images: %s", error)
            return 0

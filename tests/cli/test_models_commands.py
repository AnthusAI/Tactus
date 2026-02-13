"""
Tests for models CLI commands.
"""

import tempfile

from typer.testing import CliRunner

from tactus.cli.commands.models import app
from tactus.registry.local import LocalRegistry

runner = CliRunner()


class TestModelsListCommand:
    """Test 'models list' command."""

    def test_list_no_versions(self):
        """Test listing when no versions exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, ["list", "nonexistent", "--registry-dir", tmpdir])

            assert result.exit_code == 0
            assert "No versions found" in result.stdout

    def test_list_with_versions(self):
        """Test listing existing versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Register some versions
            registry = LocalRegistry(registry_dir=tmpdir)
            registry.register(
                name="classifier",
                version="v1.0.0",
                backend_type="pytorch",
                backend_config={"path": "/models/v1.pt"},
                tags=["latest"],
            )
            registry.register(
                name="classifier",
                version="v2.0.0",
                backend_type="pytorch",
                backend_config={"path": "/models/v2.pt"},
                tags=["champion"],
            )

            result = runner.invoke(app, ["list", "classifier", "--registry-dir", tmpdir])

            assert result.exit_code == 0
            assert "Versions for model 'classifier'" in result.stdout
            assert "v1.0.0" in result.stdout
            assert "v2.0.0" in result.stdout
            assert "pytorch" in result.stdout
            assert "latest" in result.stdout
            assert "champion" in result.stdout
            assert "Total: 2 version(s)" in result.stdout

    def test_list_shows_header(self):
        """Test that list command shows proper header."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = LocalRegistry(registry_dir=tmpdir)
            registry.register(
                name="test",
                version="v1.0.0",
                backend_type="http",
                backend_config={"endpoint": "http://test"},
            )

            result = runner.invoke(app, ["list", "test", "--registry-dir", tmpdir])

            assert result.exit_code == 0
            assert "VERSION" in result.stdout
            assert "BACKEND" in result.stdout
            assert "TAGS" in result.stdout
            assert "CREATED" in result.stdout


class TestModelsPromoteCommand:
    """Test 'models promote' command."""

    def test_promote_success(self):
        """Test successful promotion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Register a version
            registry = LocalRegistry(registry_dir=tmpdir)
            registry.register(
                name="classifier",
                version="v1.0.0",
                backend_type="http",
                backend_config={"endpoint": "http://example.com"},
            )

            result = runner.invoke(
                app, ["promote", "classifier", "v1.0.0", "champion", "--registry-dir", tmpdir]
            )

            assert result.exit_code == 0
            assert "Promoted classifier version v1.0.0 to tag 'champion'" in result.stdout

            # Verify tag was applied
            version = registry.resolve("classifier", "champion")
            assert version.version_id == "v1.0.0"

    def test_promote_moves_existing_tag(self):
        """Test that promotion moves existing tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = LocalRegistry(registry_dir=tmpdir)

            # Register two versions
            registry.register(
                name="classifier",
                version="v1.0.0",
                backend_type="http",
                backend_config={"endpoint": "http://v1.com"},
                tags=["champion"],
            )
            registry.register(
                name="classifier",
                version="v2.0.0",
                backend_type="http",
                backend_config={"endpoint": "http://v2.com"},
            )

            # Promote v2 to champion
            result = runner.invoke(
                app, ["promote", "classifier", "v2.0.0", "champion", "--registry-dir", tmpdir]
            )

            assert result.exit_code == 0
            assert "Promoted classifier version v2.0.0 to tag 'champion'" in result.stdout
            assert "Previous champion version v1.0.0" in result.stdout
            assert "champion-previous" in result.stdout

            # Verify tags
            champion = registry.resolve("classifier", "champion")
            assert champion.version_id == "v2.0.0"

            previous = registry.resolve("classifier", "champion-previous")
            assert previous.version_id == "v1.0.0"

    def test_promote_nonexistent_version(self):
        """Test promoting nonexistent version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app,
                ["promote", "classifier", "v1.0.0", "champion", "--registry-dir", tmpdir],
            )

            assert result.exit_code == 1
            assert "Error promoting version" in result.stdout

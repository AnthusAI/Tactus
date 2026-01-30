import subprocess
from pathlib import Path


from tactus.sandbox import docker_manager


def test_resolve_dockerfile_path_prefers_source(tmp_path):
    (tmp_path / "tactus" / "docker").mkdir(parents=True)
    (tmp_path / "tactus" / "docker" / "Dockerfile").write_text("FROM scratch\n")
    (tmp_path / "pyproject.toml").write_text("name = 'tactus'\n")
    (tmp_path / "README.md").write_text("readme\n")

    dockerfile, mode = docker_manager.resolve_dockerfile_path(tmp_path)

    assert mode == "source"
    assert dockerfile.name == "Dockerfile"


def test_resolve_dockerfile_path_uses_pypi_when_no_source(tmp_path):
    docker_dir = tmp_path / "tactus" / "docker"
    docker_dir.mkdir(parents=True)
    (docker_dir / "Dockerfile.pypi").write_text("FROM scratch\n")

    dockerfile, mode = docker_manager.resolve_dockerfile_path(tmp_path)

    assert mode == "pypi"
    assert dockerfile.name == "Dockerfile.pypi"


def test_calculate_source_hash_ignores_pycache(tmp_path):
    root = tmp_path
    (root / "tactus" / "core").mkdir(parents=True)
    (root / "tactus" / "core" / "__pycache__").mkdir(parents=True)
    (root / "tactus" / "core" / "__pycache__" / "cache.py").write_text("noop\n")
    (root / "tactus" / "core" / "main.py").write_text("print('hi')\n")
    (root / "pyproject.toml").write_text("name = 'tactus'\n")

    digest = docker_manager.calculate_source_hash(root)

    assert isinstance(digest, str)
    assert len(digest) == 16


def test_calculate_source_hash_skips_pyc_and_ds_store(tmp_path):
    root = tmp_path
    (root / "tactus" / "core").mkdir(parents=True)
    (root / "tactus" / "core" / "__pycache__").mkdir(parents=True)
    (root / "tactus" / "core" / "main.pyc").write_bytes(b"nope")
    (root / "tactus" / "core" / ".DS_Store").write_bytes(b"nope")
    (root / "tactus" / "core" / "main.py").write_text("print('hi')\n")
    (root / "pyproject.toml").write_text("name = 'tactus'\n")

    digest = docker_manager.calculate_source_hash(root)

    assert isinstance(digest, str)
    assert len(digest) == 16


def test_calculate_source_hash_handles_missing_paths(tmp_path):
    digest = docker_manager.calculate_source_hash(tmp_path)

    assert isinstance(digest, str)
    assert len(digest) == 16


def test_calculate_source_hash_handles_non_file_non_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(docker_manager.Path, "exists", lambda _self: True)
    monkeypatch.setattr(docker_manager.Path, "is_file", lambda _self: False)
    monkeypatch.setattr(docker_manager.Path, "is_dir", lambda _self: False)

    digest = docker_manager.calculate_source_hash(tmp_path)

    assert isinstance(digest, str)
    assert len(digest) == 16


def test_is_docker_available_reports_missing_cli(monkeypatch):
    monkeypatch.setattr(docker_manager.shutil, "which", lambda _name: None)

    available, reason = docker_manager.is_docker_available()

    assert available is False
    assert "Docker CLI not found" in reason


def test_is_docker_available_reports_daemon_not_running(monkeypatch):
    monkeypatch.setattr(docker_manager.shutil, "which", lambda _name: "/usr/bin/docker")

    class Result:
        returncode = 1
        stderr = "Cannot connect to the Docker daemon"

    monkeypatch.setattr(docker_manager.subprocess, "run", lambda *args, **kwargs: Result())

    available, reason = docker_manager.is_docker_available()

    assert available is False
    assert "daemon not running" in reason


def test_is_docker_available_reports_permission_denied(monkeypatch):
    monkeypatch.setattr(docker_manager.shutil, "which", lambda _name: "/usr/bin/docker")

    class Result:
        returncode = 1
        stderr = "permission denied"

    monkeypatch.setattr(docker_manager.subprocess, "run", lambda *args, **kwargs: Result())

    available, reason = docker_manager.is_docker_available()

    assert available is False
    assert "Permission denied" in reason


def test_is_docker_available_reports_other_error(monkeypatch):
    monkeypatch.setattr(docker_manager.shutil, "which", lambda _name: "/usr/bin/docker")

    class Result:
        returncode = 1
        stderr = "boom"

    monkeypatch.setattr(docker_manager.subprocess, "run", lambda *args, **kwargs: Result())

    available, reason = docker_manager.is_docker_available()

    assert available is False
    assert "Docker error" in reason


def test_is_docker_available_handles_timeout(monkeypatch):
    monkeypatch.setattr(docker_manager.shutil, "which", lambda _name: "/usr/bin/docker")

    def raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="docker", timeout=10)

    monkeypatch.setattr(docker_manager.subprocess, "run", raise_timeout)

    available, reason = docker_manager.is_docker_available()

    assert available is False
    assert "timeout" in reason


def test_is_docker_available_handles_file_not_found(monkeypatch):
    monkeypatch.setattr(docker_manager.shutil, "which", lambda _name: "/usr/bin/docker")

    def raise_not_found(*_args, **_kwargs):
        raise FileNotFoundError("missing")

    monkeypatch.setattr(docker_manager.subprocess, "run", raise_not_found)

    available, reason = docker_manager.is_docker_available()

    assert available is False
    assert "Docker CLI not found" in reason


def test_is_docker_available_returns_success(monkeypatch):
    monkeypatch.setattr(docker_manager.shutil, "which", lambda _name: "/usr/bin/docker")

    class Result:
        returncode = 0
        stderr = ""
        stdout = "ok"

    monkeypatch.setattr(docker_manager.subprocess, "run", lambda *args, **kwargs: Result())

    available, reason = docker_manager.is_docker_available()

    assert available is True
    assert reason == ""


def test_is_docker_available_handles_unexpected_exception(monkeypatch):
    monkeypatch.setattr(docker_manager.shutil, "which", lambda _name: "/usr/bin/docker")

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(docker_manager.subprocess, "run", raise_error)

    available, reason = docker_manager.is_docker_available()

    assert available is False
    assert "Docker check failed" in reason


def test_docker_manager_needs_rebuild_variants(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")

    monkeypatch.setattr(manager, "image_exists", lambda: False)
    assert manager.needs_rebuild("1.0") is True

    monkeypatch.setattr(manager, "image_exists", lambda: True)
    monkeypatch.setattr(manager, "get_image_version", lambda: None)
    assert manager.needs_rebuild("1.0") is True

    monkeypatch.setattr(manager, "get_image_version", lambda: "0.9")
    assert manager.needs_rebuild("1.0") is True

    monkeypatch.setattr(manager, "get_image_version", lambda: "1.0")
    monkeypatch.setattr(manager, "get_image_source_hash", lambda: "old")
    assert manager.needs_rebuild("1.0", current_hash="new") is True

    monkeypatch.setattr(manager, "get_image_source_hash", lambda: None)
    assert manager.needs_rebuild("1.0", current_hash="new") is True

    monkeypatch.setattr(manager, "get_image_source_hash", lambda: "match")
    assert manager.needs_rebuild("1.0", current_hash="match") is False

    monkeypatch.setattr(manager, "get_image_source_hash", lambda: "match")
    assert manager.needs_rebuild("1.0", current_hash=None) is False


def test_build_image_rejects_missing_paths(tmp_path):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")

    ok, msg = manager.build_image(tmp_path / "missing.Dockerfile", tmp_path, version="1.0")
    assert ok is False
    assert "Dockerfile not found" in msg

    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n")
    ok, msg = manager.build_image(dockerfile, tmp_path / "missing", version="1.0")
    assert ok is False
    assert "Build context not found" in msg


def test_build_image_success(monkeypatch, tmp_path):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n")
    context = tmp_path / "context"
    context.mkdir()

    class Result:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(docker_manager.subprocess, "run", lambda *args, **kwargs: Result())

    ok, msg = manager.build_image(dockerfile, context, version="1.0", source_hash="abc")

    assert ok is True
    assert "Successfully built" in msg


def test_build_image_verbose_success(monkeypatch, tmp_path):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n")
    context = tmp_path / "context"
    context.mkdir()

    class FakeStdout:
        def __init__(self):
            self._lines = iter(["step 1\n", "", "step 2\n", ""])

        def readline(self):
            return next(self._lines)

    class FakeProcess:
        def __init__(self):
            self.stdout = FakeStdout()
            self.returncode = 0

        def wait(self):
            return 0

    monkeypatch.setattr(docker_manager.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    ok, msg = manager.build_image(dockerfile, context, version="1.0", verbose=True)
    assert ok is True
    assert "Successfully built" in msg


def test_build_image_verbose_skips_falsey_lines(monkeypatch, tmp_path):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n")
    context = tmp_path / "context"
    context.mkdir()

    class FakeStdout:
        def __init__(self):
            self._lines = iter(["step 1\n", None, ""])

        def readline(self):
            return next(self._lines)

    class FakeProcess:
        def __init__(self):
            self.stdout = FakeStdout()
            self.returncode = 0

        def wait(self):
            return 0

    monkeypatch.setattr(docker_manager.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    ok, msg = manager.build_image(dockerfile, context, version="1.0", verbose=True)
    assert ok is True
    assert "Successfully built" in msg


def test_build_image_verbose_failure(monkeypatch, tmp_path):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n")
    context = tmp_path / "context"
    context.mkdir()

    class FakeStdout:
        def __init__(self):
            self._lines = iter(["error\n", ""])

        def readline(self):
            return next(self._lines)

    class FakeProcess:
        def __init__(self):
            self.stdout = FakeStdout()
            self.returncode = 1

        def wait(self):
            return 1

    monkeypatch.setattr(docker_manager.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

    ok, msg = manager.build_image(dockerfile, context, version="1.0", verbose=True)
    assert ok is False
    assert "Build failed" in msg


def test_build_image_timeout(monkeypatch, tmp_path):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n")
    context = tmp_path / "context"
    context.mkdir()

    def raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="docker", timeout=600)

    monkeypatch.setattr(docker_manager.subprocess, "run", raise_timeout)

    ok, msg = manager.build_image(dockerfile, context, version="1.0")
    assert ok is False
    assert "Build timed out" in msg


def test_build_image_exception(monkeypatch, tmp_path):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM scratch\n")
    context = tmp_path / "context"
    context.mkdir()

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(docker_manager.subprocess, "run", raise_error)

    ok, msg = manager.build_image(dockerfile, context, version="1.0")
    assert ok is False
    assert "boom" in msg


def test_ensure_image_exists_returns_up_to_date(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")
    monkeypatch.setattr(manager, "needs_rebuild", lambda _version: False)

    ok, msg = manager.ensure_image_exists(Path("Dockerfile"), Path("."), version="1.0")

    assert ok is True
    assert "up to date" in msg


def test_ensure_image_exists_force_rebuild(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")
    monkeypatch.setattr(manager, "build_image", lambda *args, **kwargs: (True, "built"))

    ok, msg = manager.ensure_image_exists(
        Path("Dockerfile"), Path("."), version="1.0", force_rebuild=True
    )
    assert ok is True
    assert msg == "built"


def test_remove_image_noop_when_missing(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")
    monkeypatch.setattr(manager, "image_exists", lambda: False)

    ok, msg = manager.remove_image()

    assert ok is True
    assert "does not exist" in msg


def test_remove_image_failure(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")
    monkeypatch.setattr(manager, "image_exists", lambda: True)

    class Result:
        returncode = 1
        stderr = "fail"

    monkeypatch.setattr(docker_manager.subprocess, "run", lambda *args, **kwargs: Result())

    ok, msg = manager.remove_image()
    assert ok is False
    assert "Failed to remove image" in msg


def test_remove_image_success(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")
    monkeypatch.setattr(manager, "image_exists", lambda: True)

    class Result:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(docker_manager.subprocess, "run", lambda *args, **kwargs: Result())

    ok, msg = manager.remove_image()
    assert ok is True
    assert "Removed" in msg


def test_remove_image_exception(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")
    monkeypatch.setattr(manager, "image_exists", lambda: True)

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(docker_manager.subprocess, "run", raise_error)

    ok, msg = manager.remove_image()
    assert ok is False
    assert "boom" in msg


def test_cleanup_old_images_removes(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")

    def fake_run(args, **_kwargs):
        if args[:2] == ["docker", "images"]:

            class Result:
                returncode = 0
                stdout = "img:old\nimg:local\n\nimg\n"

            return Result()

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(docker_manager.subprocess, "run", fake_run)

    removed = manager.cleanup_old_images()
    assert removed == 1


def test_cleanup_old_images_respects_keep_tags(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")

    def fake_run(args, **_kwargs):
        if args[:2] == ["docker", "images"]:

            class Result:
                returncode = 0
                stdout = "img:old\nimg:keep\n"

            return Result()

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(docker_manager.subprocess, "run", fake_run)

    removed = manager.cleanup_old_images(keep_tags=["keep"])
    assert removed == 1


def test_cleanup_old_images_skips_failed_removal(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")
    calls = []

    def fake_run(args, **_kwargs):
        if args[:2] == ["docker", "images"]:

            class Result:
                returncode = 0
                stdout = "img:old\n"

            return Result()
        calls.append(args)

        class Result:
            returncode = 1
            stdout = ""
            stderr = "fail"

        return Result()

    monkeypatch.setattr(docker_manager.subprocess, "run", fake_run)

    removed = manager.cleanup_old_images()
    assert removed == 0
    assert calls


def test_cleanup_old_images_handles_error(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")

    class Result:
        returncode = 1
        stdout = ""
        stderr = "err"

    monkeypatch.setattr(docker_manager.subprocess, "run", lambda *args, **kwargs: Result())
    assert manager.cleanup_old_images() == 0


def test_cleanup_old_images_handles_exception(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(docker_manager.subprocess, "run", raise_error)
    assert manager.cleanup_old_images() == 0


def test_image_exists_handles_timeout(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")

    def raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="docker", timeout=10)

    monkeypatch.setattr(docker_manager.subprocess, "run", raise_timeout)
    assert manager.image_exists() is False


def test_image_exists_returns_true(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")

    class Result:
        returncode = 0

    monkeypatch.setattr(docker_manager.subprocess, "run", lambda *args, **kwargs: Result())

    assert manager.image_exists() is True


def test_get_image_version_and_hash(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")

    class Result:
        returncode = 0
        stdout = "1.0\n"
        stderr = ""

    monkeypatch.setattr(docker_manager.subprocess, "run", lambda *args, **kwargs: Result())
    assert manager.get_image_version() == "1.0"

    class HashResult:
        returncode = 0
        stdout = "abc\n"
        stderr = ""

    monkeypatch.setattr(docker_manager.subprocess, "run", lambda *args, **kwargs: HashResult())
    assert manager.get_image_source_hash() == "abc"


def test_get_image_version_and_hash_failures(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")

    class Result:
        returncode = 1
        stdout = ""
        stderr = "fail"

    monkeypatch.setattr(docker_manager.subprocess, "run", lambda *args, **kwargs: Result())
    assert manager.get_image_version() is None

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(docker_manager.subprocess, "run", raise_error)
    assert manager.get_image_source_hash() is None


def test_get_image_version_exception(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")

    def raise_error(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(docker_manager.subprocess, "run", raise_error)
    assert manager.get_image_version() is None


def test_get_image_source_hash_empty_stdout(monkeypatch):
    manager = docker_manager.DockerManager(image_name="img", image_tag="tag")

    class Result:
        returncode = 0
        stdout = ""

    monkeypatch.setattr(docker_manager.subprocess, "run", lambda *args, **kwargs: Result())
    assert manager.get_image_source_hash() is None

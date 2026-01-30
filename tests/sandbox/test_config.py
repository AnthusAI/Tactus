from tactus.sandbox.config import SandboxConfig, get_default_sandbox_config


def test_default_volumes_not_duplicated():
    config = SandboxConfig(volumes=[".:/workspace:rw"])
    assert config.volumes[0] == ".:/workspace:rw"
    assert config.volumes.count(".:/workspace:rw") == 1


def test_get_default_sandbox_config():
    config = get_default_sandbox_config()
    assert isinstance(config, SandboxConfig)

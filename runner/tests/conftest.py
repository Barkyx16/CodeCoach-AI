import shutil
import subprocess

import pytest

from app.config import RunnerSettings

TOKEN = "t" * 40


def make_settings(**overrides) -> RunnerSettings:
    base = dict(runner_token=TOKEN, warmup_on_start=False, _env_file=None)
    base.update(overrides)
    return RunnerSettings(**base)


def _sandbox_available() -> bool:
    if shutil.which("docker") is None:
        return False
    info = subprocess.run(
        ["docker", "info", "--format", "{{json .Runtimes}}"], capture_output=True, text=True
    )
    if info.returncode != 0 or "runsc" not in info.stdout:
        return False
    img = subprocess.run(["docker", "image", "inspect", "codecoach-java-sandbox:21"], capture_output=True)
    return img.returncode == 0


SANDBOX_AVAILABLE = _sandbox_available()
requires_sandbox = pytest.mark.skipif(
    not SANDBOX_AVAILABLE, reason="needs Docker + gVisor runtime + codecoach-java-sandbox:21 image"
)

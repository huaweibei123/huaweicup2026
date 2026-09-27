"""Stdlib-only Colab connectivity probe; no GPU, credentials, or Drive access."""
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix="huaweicup-preflight-") as folder:
    path = Path(folder) / "roundtrip.txt"
    path.write_text("huaweicup-q1-cpu")
    assert path.read_text() == "huaweicup-q1-cpu"

print(json.dumps({
    "probe": "huaweicup-q1-cpu-v1",
    "python": sys.version.split()[0],
    "platform": platform.system(),
    "architecture": platform.machine(),
    "logical_cpus": os.cpu_count(),
    "file_roundtrip_ok": True,
    "colab_runtime_env": bool(os.environ.get("COLAB_RELEASE_TAG")),
    "scope": "connectivity and file roundtrip only; not algorithm or GPU validation",
}, indent=2))

"""Driver support. Preparation only: do not import/run before separate approval."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PLAN = HERE.parent / "e2_cli_fix_static_20260924"
SCHEMA = "e2-cli-fixed-driver-v1"


def require(value, message):
    if not value:
        raise RuntimeError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value, exclusive=False):
    path = Path(path)
    data = (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.rename(temporary, path)  # Windows refuses an existing destination.
        else:
            os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def source_identity():
    manifest = read(HERE / "sources.json")
    for name, expected in manifest["driver_files"].items():
        require(digest(HERE / name) == expected, "driver hash: " + name)
    encoded = json.dumps(manifest["driver_files"], sort_keys=True,
                         separators=(",", ":")).encode("ascii")
    bundle = hashlib.sha256(encoded).hexdigest()
    require(bundle == manifest["driver_bundle_sha256"], "bundle hash")
    return manifest


def contract():
    return read(HERE / "contract.json")


def matrix():
    return read(PLAN / "matrix.json")


def gated_request():
    """Only controlled children can reach target imports/launches."""
    require(contract()["execution_blockers"] == [], "unresolved driver execution blockers")
    require(sys.flags.utf8_mode == 1 and sys.dont_write_bytecode, "explicit UTF-8/no-bytecode policy")
    case = Path(os.environ["E2_CASE_DIR"]).resolve()
    request = read(case / "request.private.json")
    require(case == Path(request["case_directory"]).resolve(), "case directory")
    require(request["schema"] == SCHEMA, "request schema")
    require(request["nonce"] == os.environ["E2_CASE_NONCE"], "case nonce")
    manifest = source_identity()
    require(request["bundle"] == manifest["driver_bundle_sha256"], "request bundle")
    approval = read(Path(request["run_directory"]) / "approval.json")
    require(approval.get("approved") is True and
            approval.get("execution_enabled") is True and
            approval.get("runtime_review_closed") is True, "execution unapproved")
    require(approval["driver_bundle_sha256"] == request["bundle"], "approval bundle")
    require(digest(HERE / "sources.json") == approval["sources_sha256"], "approval source manifest")
    return case, request


def wait_record(path, deadline_tick, api):
    while api.tick() < deadline_tick:
        if Path(path).is_file():
            try:
                return read(path)
            except (json.JSONDecodeError, OSError):
                pass  # An in-progress evidence write, not a target retry.
        time.sleep(0.005)
    raise TimeoutError("handshake deadline: " + Path(path).name)


def expected_stdin(row):
    return bytes(range(256)) * (16 if row["id"] == "F1" else 1)


def fake_argv(row):
    return ["", "空 格", 'quote"x', "tail\\", "C:\\空间 路径\\x"]


def route_line(problem):
    return (f"[E2 ROUTE] P{problem} E0 full diagnostics; native search scorer not used\n").encode()

"""Discriminate the ADR-0018 acceptance drill embedded in compile.yml.

The drill only ever executes inside a GitHub Actions job with GHCR credentials,
so its controls shipped once without a single local execution and a negative
control silently failed to discriminate. These tests extract the real drill
source from the workflow and run it against a fake registry, so every control
is exercised without a registry.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "compile.yml"
_DRILL_MARKER = '"""ADR-0018 acceptance drill.'

REGISTRY = "ghcr.io/example/packets"
SEMANTIC_HASH = "sha256:" + "ab" * 32
PACKET_ID = "packet:topology:example"

_MANIFEST = json.dumps({"packet_id": PACKET_ID, "semantic_hash": SEMANTIC_HASH}).encode()
_BUNDLE_DIGEST = "sha256:" + hashlib.sha256(_MANIFEST).hexdigest()

# Raw registry manifest documents. Digests are the sha256 of these exact bytes,
# which is what the drill recomputes, so no hashing needs to be faked.
_GENUINE_RAW = b'{"schemaVersion":2,"object":"genuine"}'
_SUBSTITUTE_RAW = b'{"schemaVersion":2,"object":"substitute"}'
_GENUINE_DIGEST = "sha256:" + hashlib.sha256(_GENUINE_RAW).hexdigest()
_SUBSTITUTE_DIGEST = "sha256:" + hashlib.sha256(_SUBSTITUTE_RAW).hexdigest()

_STAGING_TAG = f"{REGISTRY}:packet-{SEMANTIC_HASH.removeprefix('sha256:')}"
_DRILL_TAG = f"{REGISTRY}:drill-1-1"


def _drill_source() -> str:
    """Return the acceptance drill exactly as the workflow will execute it."""

    text = WORKFLOW.read_text(encoding="utf-8")
    for body, _ in re.findall(r"python - <<'PY'\n(.*?)\n( *)PY\n", text, re.S):
        source = textwrap.dedent(body)
        if source.lstrip().startswith(_DRILL_MARKER):
            return source
    raise AssertionError("compile.yml no longer embeds the ADR-0018 acceptance drill")


class _Completed:
    def __init__(self, returncode: int = 0, stdout: Any = "", stderr: Any = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _FakeRegistry:
    """A registry where the drill tag has already moved to the substitute."""

    def __init__(self) -> None:
        self.tags = {_STAGING_TAG: _GENUINE_DIGEST, _DRILL_TAG: _SUBSTITUTE_DIGEST}
        self.raw = {_GENUINE_DIGEST: _GENUINE_RAW, _SUBSTITUTE_DIGEST: _SUBSTITUTE_RAW}

    def digest_of(self, reference: str) -> str:
        if "@sha256:" in reference:
            return reference.rsplit("@", 1)[1]
        return self.tags[reference]

    def run(self, command: list[str], **_: Any) -> _Completed:
        if command[:4] == ["docker", "buildx", "imagetools", "inspect"]:
            return _Completed(0, stdout=self.raw[self.digest_of(command[-1])])
        if command[:2] == ["docker", "pull"]:
            return _Completed(0, "pulled\n")
        if command[:2] == ["docker", "create"]:
            return _Completed(0, f"container-{self.digest_of(command[2])}\n")
        if command[:2] == ["docker", "cp"]:
            destination = Path(command[3])
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "manifest.json").write_bytes(_MANIFEST)
            # The substitute is a valid object carrying the very same packet
            # bundle plus one extra file. Packet identity alone cannot tell it
            # apart from the genuine object.
            if _SUBSTITUTE_DIGEST in command[2]:
                (destination / "substitution.marker").write_text("substituted-but-valid")
            return _Completed(0)
        if command[:2] == ["docker", "rm"]:
            return _Completed(0)
        if "validate-packet" in command:
            return _Completed(0, "validated\n")
        raise AssertionError(f"drill issued an unexpected command: {command}")


def _execute_drill(source: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    """Run the drill with a fake registry, returning its exit code."""

    registry = _FakeRegistry()
    for name, value in {
        "PACKET_REGISTRY": REGISTRY,
        "PACKET_OCI_REF": f"{REGISTRY}@{_GENUINE_DIGEST}",
        "PUSH_MANIFEST_DIGEST": _GENUINE_DIGEST,
        "STAGING_TAG_REF": _STAGING_TAG,
        "SUBSTITUTE_OCI_REF": f"{REGISTRY}@{_SUBSTITUTE_DIGEST}",
        "DRILL_TAG_REF": _DRILL_TAG,
        "EXPECTED_PACKET_ID": PACKET_ID,
        "EXPECTED_SEMANTIC_HASH": SEMANTIC_HASH,
        "EXPECTED_BUNDLE_MANIFEST_DIGEST": _BUNDLE_DIGEST,
        "RUNNER_TEMP": str(tmp_path),
        "TOPOLOGY_PYTHON": sys.executable,
        "TOPOLOGY_SRC": str(ROOT / "src"),
    }.items():
        monkeypatch.setenv(name, value)

    fake_subprocess = type(
        "_Subprocess",
        (),
        {"run": staticmethod(registry.run), "CalledProcessError": subprocess.CalledProcessError},
    )
    monkeypatch.setitem(sys.modules, "subprocess", fake_subprocess)
    try:
        exec(compile(source, "compile.yml::drill", "exec"), {"__name__": "__drill__"})
    except SystemExit as stop:
        return int(stop.code or 0)
    return 0


def test_acceptance_drill_passes_every_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _execute_drill(_drill_source(), tmp_path, monkeypatch) == 0
    output = capsys.readouterr().out
    assert "ADR-0018 acceptance drill complete" in output
    for control in (
        "PASS semantic-hash staging",
        "PASS exact packet and manifest identity accepted",
        "PASS substitute is a valid packet sharing the expected semantic hash",
        "PASS valid-object substitution",
        "PASS mutable-tag reference",
        "PASS mutable drill-tag reference",
    ):
        assert control in output, output


def test_acceptance_without_expected_registry_digest_accepts_a_substitute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The regression this test exists for.

    ``worker/packet_store.py::verify_published`` binds the reference to the
    digest publication actually returned. Without that binding, acceptance only
    proves an object is internally consistent and carries the expected packet,
    so a valid object holding the same bundle plus extra content is accepted and
    the substitution control reports a false pass.
    """

    weakened = re.sub(
        r'\n *if uri_digest != expected\["registry_manifest_digest"\]:\n'
        r"(?: +.*\n)*? +\)\n",
        "\n",
        _drill_source(),
        count=1,
    )
    assert weakened != _drill_source(), "expected-registry-digest control not found in the drill"

    assert _execute_drill(weakened, tmp_path, monkeypatch) == 1
    assert "FAIL valid-object substitution" in capsys.readouterr().err

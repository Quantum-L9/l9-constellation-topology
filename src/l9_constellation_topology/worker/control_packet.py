"""CLI for validating payload contracts and emitting signed TransportPacket files."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from l9_constellation_topology.io import (
    FileSystemOutputSink,
    RenderedArtifact,
    WriteIntent,
    WritePolicy,
)
from l9_constellation_topology.packets import (
    GitHubIngressPayload,
    RenderRequestPayload,
    ReplayRequestPayload,
    StageDispatchPayload,
    ValidationRequestPayload,
)
from l9_constellation_topology.run import (
    artifact_hash,
    canonical_bytes,
    canonical_json,
    semantic_hash,
)

from .transport_factory import build_transport_packet

PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "l9.github-ingress/1.0.0": GitHubIngressPayload,
    "l9.stage-dispatch/1.0.0": StageDispatchPayload,
    "l9.replay-request/1.0.0": ReplayRequestPayload,
    "l9.render-request/1.0.0": RenderRequestPayload,
    "l9.validation-request/1.0.0": ValidationRequestPayload,
}


def _load_payload(path: Path) -> BaseModel:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read payload JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("control payload must be a JSON object")
    schema = raw.get("payload_schema")
    model = PAYLOAD_MODELS.get(str(schema))
    if model is None:
        raise ValueError(f"unsupported control payload schema: {schema}")
    return model.model_validate(raw)


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="l9-topology-control-packet")
    parser.add_argument("--payload-file", required=True)
    parser.add_argument("--action", required=True)
    parser.add_argument("--packet-type", choices=("command", "event"), default="command")
    parser.add_argument("--idempotency-key")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--workflow-id")
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--key-id", default=os.environ.get("L9_DISPATCH_HMAC_KEY_ID", "foundational-hmac-v1")
    )
    args = parser.parse_args(argv)

    key = os.environ.get("L9_DISPATCH_HMAC_KEY")
    if not key:
        raise ValueError("L9_DISPATCH_HMAC_KEY is required")
    payload = _load_payload(Path(args.payload_file))
    idempotency_key = args.idempotency_key or semantic_hash(payload)
    packet = build_transport_packet(
        payload=payload,
        packet_type=args.packet_type,
        action=args.action,
        idempotency_key=idempotency_key,
        trace_id=args.trace_id,
        correlation_id=args.correlation_id,
        workflow_id=args.workflow_id,
        key=key.encode("utf-8"),
        key_id=args.key_id,
        provenance={"resolved_by_gate": False, "resolver": "l9-ci-core"},
        governance={},
    )
    content = canonical_bytes(packet) + b"\n"
    output = Path(args.out).resolve()
    artifact = RenderedArtifact(
        logical_id="signed-transport-packet",
        destination_path=output.name,
        artifact_kind="debug-artifact",
        media_type="application/json",
        content=content,
        content_hash=artifact_hash(content),
        semantic_hash=semantic_hash(packet),
    )
    sink = FileSystemOutputSink(
        output.parent,
        WritePolicy(
            allowed_output_roots=(".",),
            allowed_artifact_kinds=("debug-artifact",),
            allow_overwrite=False,
            require_expected_hash_for_replace=True,
        ),
    )
    sink.enqueue(WriteIntent(artifact=artifact))
    receipt = sink.commit()
    if receipt.status != "passed":
        raise RuntimeError(receipt.model_dump_json())
    print(canonical_json({"packet_id": packet.header.packet_id, "output": str(output)}))
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()

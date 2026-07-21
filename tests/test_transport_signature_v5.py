import pytest

from l9_constellation_topology.packets import (
    GitHubIngressData,
    GitHubIngressPayload,
    StageProfileRef,
)
from l9_constellation_topology.worker import (
    WorkerError,
    build_transport_packet,
    verify_transport_packet,
)

KEY = b"test-foundational-key"
KEY_ID = "foundational-hmac-v1"


def ingress_payload() -> GitHubIngressPayload:
    return GitHubIngressPayload(
        data=GitHubIngressData(
            event_name="push",
            target_repository="Quantum-L9/l9-constellation-topology",
            target_revision="git:abc123",
            profile=StageProfileRef(
                id="foundational-topology",
                version="1.0.0",
                hash="sha256:profile",
            ),
        )
    )


def test_transport_signature_round_trip_and_tamper_detection() -> None:
    packet = build_transport_packet(
        payload=ingress_payload(),
        packet_type="event",
        action="compile-topology",
        idempotency_key="sha256:idempotent",
        trace_id="trace:test",
        correlation_id="correlation:test",
        workflow_id="foundational-repository-intelligence",
        key=KEY,
        key_id=KEY_ID,
        provenance={"resolved_by_gate": False, "resolver": "l9-ci-core"},
    )
    verify_transport_packet(
        packet,
        key=KEY,
        allowed_algorithms=("hmac-sha256",),
        allowed_key_ids=(KEY_ID,),
    )

    tampered = packet.model_copy(
        update={
            "payload": {
                **packet.payload,
                "data": {**packet.payload["data"], "target_revision": "git:tampered"},
            }
        }
    )
    with pytest.raises(WorkerError, match="transport-packet-id-mismatch"):
        verify_transport_packet(
            tampered,
            key=KEY,
            allowed_algorithms=("hmac-sha256",),
            allowed_key_ids=(KEY_ID,),
        )


def test_transport_signature_rejects_unapproved_key_identity() -> None:
    packet = build_transport_packet(
        payload=ingress_payload(),
        packet_type="event",
        action="compile-topology",
        idempotency_key="sha256:idempotent",
        trace_id="trace:test",
        correlation_id="correlation:test",
        workflow_id="foundational-repository-intelligence",
        key=KEY,
        key_id="wrong-key",
    )
    with pytest.raises(WorkerError, match="transport-signature-missing"):
        verify_transport_packet(
            packet,
            key=KEY,
            allowed_algorithms=("hmac-sha256",),
            allowed_key_ids=(KEY_ID,),
        )

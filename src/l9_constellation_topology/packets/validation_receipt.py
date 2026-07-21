"""Immutable validation receipts and deterministic receipt identity."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from l9_constellation_topology.domain.base import FrozenModel
from l9_constellation_topology.run.evidence import semantic_hash, utc_now

from .common import Producer, ValidationStatus


class ValidationCheck(FrozenModel):
    check_id: str
    check_class: Literal["schema", "invariant", "evidence", "cross-reference"]
    rule: str
    status: Literal["passed", "failed", "blocked", "not_run"]
    message: str
    path: str | None = None
    evidence_refs: tuple[str, ...] = ()
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationReceipt(FrozenModel):
    packet_type: Literal["l9.validation-receipt"] = "l9.validation-receipt"
    packet_version: str = "1.0.0"
    receipt_id: str
    subject_packet_id: str
    subject_semantic_hash: str
    validator: Producer
    status: ValidationStatus
    schema_results: tuple[ValidationCheck, ...] = ()
    invariant_results: tuple[ValidationCheck, ...] = ()
    evidence_results: tuple[ValidationCheck, ...] = ()
    cross_reference_results: tuple[ValidationCheck, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)
    semantic_hash: str


def validation_receipt_semantic_view(receipt: ValidationReceipt) -> dict[str, object]:
    return {
        "packet_type": receipt.packet_type,
        "packet_version": receipt.packet_version,
        "subject_packet_id": receipt.subject_packet_id,
        "subject_semantic_hash": receipt.subject_semantic_hash,
        "validator": receipt.validator,
        "status": receipt.status,
        "schema_results": receipt.schema_results,
        "invariant_results": receipt.invariant_results,
        "evidence_results": receipt.evidence_results,
        "cross_reference_results": receipt.cross_reference_results,
    }


def finalize_validation_receipt(candidate: ValidationReceipt) -> ValidationReceipt:
    digest = semantic_hash(validation_receipt_semantic_view(candidate))
    return candidate.model_copy(
        update={
            "receipt_id": f"receipt:{digest.removeprefix('sha256:')}",
            "semantic_hash": digest,
        }
    )


def validate_validation_receipt(receipt: ValidationReceipt) -> None:
    calculated = semantic_hash(validation_receipt_semantic_view(receipt))
    if receipt.semantic_hash != calculated:
        raise ValueError(
            "validation-receipt-hash-mismatch: "
            f"expected {receipt.semantic_hash}, calculated {calculated}"
        )
    expected_id = f"receipt:{calculated.removeprefix('sha256:')}"
    if receipt.receipt_id != expected_id:
        raise ValueError(
            f"validation-receipt-id-mismatch: expected {expected_id}, got {receipt.receipt_id}"
        )

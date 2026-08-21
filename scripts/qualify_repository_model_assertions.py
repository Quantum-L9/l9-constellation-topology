#!/usr/bin/env python3
"""Qualify assertion activation against real, externally produced RMP 1.1 bundles.

The checked-in fixture proves the pipeline works on a tree shaped to exercise it.
That is necessary and not sufficient: a fixture can be shaped, however honestly,
to the behaviour it is meant to demonstrate. Qualification runs the same pipeline
over repository-model packets emitted by the bound ``l9-meta-injector`` from
repositories this repository did not author, and records what survived.

Bundles are named on the command line::

    qualify_repository_model_assertions.py \\
        --bundle golden-repo=/path/to/rmp/golden-repo \\
        --bundle l9-ops-mcp=/path/to/rmp/l9-ops-mcp \\
        --out QUALIFICATION.json

Producing those bundles is the producer's job and happens outside this
repository::

    node scripts/repository-model-cli.js <repo> --name <name> \\
        --revision git:<sha> --out <bundle>

The compiler is never pointed at a source tree here. Its only ingress is the
packet, which is the canonical repository ingress the build specification
requires. Nothing is dispatched: this reports on a plan, and building a plan
performs no effect.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from l9_constellation_topology.compiler import compile_topology
from l9_constellation_topology.packets.loader import load_repository_model_bundle
from l9_constellation_topology.publication import (
    EFFECT_IDENTITY_ALGORITHM_VERSION,
    build_publication_plan,
    load_publication_policy,
)
from l9_constellation_topology.reconciliation import (
    PREDICATE_POLICY_VERSION,
    SUPPORTED_PREDICATES,
    predicate_support,
)

ROOT = Path(__file__).resolve().parents[1]

#: Fixed so a re-run of the same bundles produces the same report.
QUALIFICATION_TIME = datetime(2026, 7, 21, tzinfo=UTC)


def _qualify(name: str, bundle_path: Path) -> dict[str, Any]:
    """Compile one real bundle and record what its assertions became."""
    bundle = load_repository_model_bundle(bundle_path)
    packet = bundle.packet
    if packet.payload is None:
        raise ValueError(f"{name}: packet payload is unresolved")
    assertions = packet.payload.assertions or ()

    result = compile_topology(ROOT, (bundle_path,), created_at=QUALIFICATION_TIME)
    state = result.materialized.state
    plan = build_publication_plan(
        result.materialized,
        load_publication_policy(ROOT),
        published_at=QUALIFICATION_TIME,
    )

    incoming = {assertion.assertion_id for assertion in assertions}
    claimed = {
        assertion_id
        for claim in state.semantic_claims
        for assertion_id in claim.source_assertion_ids
    }
    conservation = next(
        check
        for check in result.validation_receipt.cross_reference_results
        if check.check_id == "cross-assertion-conservation"
    )
    claim_candidates = [item for item in plan.candidates if item.candidate_kind == "claim"]
    unsupported = sorted(
        {
            claim.predicate
            for claim in state.semantic_claims
            if predicate_support(claim.predicate) == "unsupported"
        }
    )

    return {
        "name": name,
        "repository_model_packet_id": packet.packet_id,
        "repository_model_packet_version": packet.packet_version,
        "repository_model_semantic_hash": packet.semantic_hash,
        "source_revision": packet.source_snapshot.revision,
        "producer": f"{packet.producer.name}/{packet.producer.version}",
        "interpretation_profile": (
            f"{packet.interpretation_profile.profile_id}/"
            f"{packet.interpretation_profile.profile_version}"
            if packet.interpretation_profile is not None
            else None
        ),
        "topology_packet_id": result.materialized.packet.packet_id,
        "topology_validation_status": result.validation_receipt.status,
        "assertion_count_in": len(assertions),
        "semantic_claim_count_out": len(state.semantic_claims),
        # The number that matters: an assertion that arrived and left no trace.
        "assertion_loss_count": len(incoming - claimed),
        "assertion_conservation_check": conservation.status,
        "predicates_in": dict(sorted(Counter(a.predicate for a in assertions).items())),
        "predicates_out": dict(
            sorted(Counter(claim.predicate for claim in state.semantic_claims).items())
        ),
        "predicates_lost": sorted(
            {a.predicate for a in assertions} - {claim.predicate for claim in state.semantic_claims}
        ),
        "unsupported_predicates_preserved": unsupported,
        "conflicts_generated": [
            {"subject_id": item.subject_id, "field": item.field, "values": list(item.values)}
            for item in state.conflicts
            if item.field in {a.predicate for a in assertions}
        ],
        "claim_derived_unknown_count": sum(
            1
            for item in state.unknowns
            if item.field in SUPPORTED_PREDICATES or item.field in {a.predicate for a in assertions}
        ),
        "topology_projection_counts": dict(
            sorted(
                Counter(
                    claim.predicate for claim in state.semantic_claims if claim.projected
                ).items()
            )
        ),
        "publication_claim_candidate_count": len(claim_candidates),
        "publication_claim_status_counts": dict(
            sorted(Counter(item.eligibility.status for item in claim_candidates).items())
        ),
        "publication_candidate_count": len(plan.candidates),
        "dispatches_performed": 0,
    }


def build_report(bundles: dict[str, Path]) -> dict[str, Any]:
    return {
        "schema": "l9.assertion-activation-qualification/v1",
        "predicate_policy_version": PREDICATE_POLICY_VERSION,
        "effect_identity_algorithm": EFFECT_IDENTITY_ALGORITHM_VERSION,
        "canonical_ingress": "repository-model-packet",
        "source_rescan_performed": False,
        "dispatches_performed": 0,
        "specimens": [_qualify(name, path) for name, path in sorted(bundles.items())],
    }


def main(argv: Sequence[str] | None = None) -> None:
    """Write or print the qualification report.

    No exit code is returned: this command either completes or raises. Bad
    arguments exit through ``parser.error``, and an unreadable or invalid
    bundle raises out of the compiler rather than being reported as a status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="A named repository-model packet bundle directory.",
    )
    parser.add_argument("--out", type=Path, help="Write the report here instead of stdout.")
    args = parser.parse_args(argv)

    bundles: dict[str, Path] = {}
    for entry in args.bundle:
        name, _, raw = entry.partition("=")
        if not name or not raw:
            parser.error(f"expected NAME=PATH, got {entry!r}")
        bundles[name] = Path(raw)
    if not bundles:
        parser.error("at least one --bundle is required")

    report = json.dumps(build_report(bundles), indent=2, sort_keys=True) + "\n"
    if args.out is None:
        print(report, end="")
        return
    # The destination comes from the command line, so it is resolved and confined
    # to this repository before anything is written. A qualification report has no
    # business landing outside the tree it reports on.
    destination = args.out.resolve()
    if not destination.is_relative_to(ROOT):
        parser.error(f"--out must stay inside {ROOT}; got {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report, encoding="utf-8")
    print(f"wrote {destination.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

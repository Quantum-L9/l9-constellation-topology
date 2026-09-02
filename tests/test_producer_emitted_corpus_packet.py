"""A bundle this repository did not build must verify, resolve, and compile.

Every other corpus fixture here is constructed in Python with this repository's
own models. That tests what the compiler does with a packet; it cannot test
whether the producer and the consumer agree, because a bundle built with the
consumer's own canonicalizer verifies against it by construction. It proves this
side self-consistent and nothing else.

``tests/fixtures/corpus_intelligence/producer-emitted`` is the output of the
real TypeScript producer, committed with a PROVENANCE.md naming the revision and
the command that regenerates it. The assertions below are the ones that were
failing when it was first generated, each against a divergence no existing test
could see:

* payload hashes declared over a different byte sequence than the one written;
* a semantic hash disagreeing because one side wrote ``"root_packet_id":null``
  where the other, canonicalizing with ``exclude_none=True``, wrote nothing;
* a canonical renderer that could not serialize a pair score at all, the two
  runtimes formatting floats differently in three ways even where their
  shortest round-trip digits agree.

Nothing here is asserted against a recorded expectation of what the producer
emits. The bundle is loaded through the same code path a real compile uses, so
these tests fail when the two sides stop agreeing — not when the producer's
output changes shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from l9_constellation_topology.packets.corpus_bundle import (
    calculate_corpus_semantic_hash,
    load_corpus_intelligence_bundle,
)
from l9_constellation_topology.packets.corpus_validator import (
    validate_corpus_intelligence_packet,
)
from l9_constellation_topology.packets.loader import (
    PacketLoadError,
    load_repository_model_bundle,
)
from l9_constellation_topology.run.evidence import artifact_hash

FIXTURE = Path(__file__).resolve().parent / "fixtures/corpus_intelligence/producer-emitted"
BUNDLE = FIXTURE / "corpus-intelligence"


@pytest.fixture(scope="module")
def bundle():
    return load_corpus_intelligence_bundle(BUNDLE)


@pytest.fixture(scope="module")
def input_packets():
    return tuple(
        load_repository_model_bundle(path).packet for path in sorted((FIXTURE / "roots").iterdir())
    )


def test_provenance_names_the_revision_it_came_from() -> None:
    """A fixture that cannot say where it came from cannot be regenerated."""
    text = (FIXTURE / "PROVENANCE.md").read_text(encoding="utf-8")
    assert "Quantum-L9/l9-meta-injector" in text
    assert "emit_corpus_intelligence_fixture.ts" in text
    # A 40-character revision, not a branch name that moves under it.
    revision = next(line for line in text.splitlines() if "Producer revision" in line)
    assert len([part for part in revision.split("`") if len(part) == 40]) == 1


def test_the_consumer_loads_what_the_producer_wrote(bundle) -> None:
    """The whole verification path, on bytes this repository did not produce."""
    assert bundle.packet.packet_type == "l9.corpus-intelligence"
    assert bundle.packet.packet_version == "1.0.0"
    assert bundle.packet.payload is not None


def test_the_semantic_hash_recomputes_to_what_the_producer_declared(bundle) -> None:
    """The two canonicalizations agree, or this is the line that says they do not.

    ``load_corpus_intelligence_bundle`` already checks this and would have
    raised; asserting it again names the property, so a failure here reads as
    "the two languages disagree" rather than as a bundle that would not open.
    """
    assert calculate_corpus_semantic_hash(bundle.packet) == bundle.packet.semantic_hash
    assert (
        bundle.packet.packet_id == f"packet:{bundle.packet.semantic_hash.removeprefix('sha256:')}"
    )


def test_every_payload_hash_is_the_hash_of_the_bytes_on_disk(bundle) -> None:
    """Declared hashes are content hashes of files, trailing newline included."""
    for field, reference in bundle.packet.payload_refs.items():
        content = (BUNDLE / reference).read_bytes()
        assert artifact_hash(content) == bundle.packet.payload_hashes[field], field
        assert content.endswith(b"\n"), field


def test_every_identity_resolves_against_the_input_packets(bundle, input_packets) -> None:
    """Parsing is not resolving.

    A packet can verify every hash it declares and still be about artifacts
    nothing observed. This is the check that distinguishes the two, and it needs
    the Repository Model bundles the packet was compiled over — which is why the
    fixture carries them.
    """
    assert len(input_packets) >= 2
    validate_corpus_intelligence_packet(bundle.packet, input_packets)


def test_the_payload_carries_every_domain_with_content(bundle) -> None:
    """A fixture whose domains are empty proves the empty case and no other."""
    payload = bundle.packet.payload
    assert len(payload.document_work_signals) > 0
    assert len(payload.exact_duplicate_relations) > 0
    assert len(payload.semantic_pair_relations) > 0
    assert len(payload.topic_candidates) > 0
    assert len(payload.project_candidates) > 0
    assert len(payload.consolidation_candidates) > 0
    assert len(payload.readiness_evidence) > 0
    assert len(payload.reasoning_candidates) > 0


def test_work_signal_locators_cross_in_every_coordinate_system(bundle) -> None:
    """Six coordinate systems, each renamed on the way across.

    A DOCX block index, a PPTX slide and shape, a PDF page, a spreadsheet cell,
    a notebook cell and an HTML node path are different shapes with different
    required fields, and the producer renames each into this repository's naming
    before emitting. A locator that arrived with the producer's own field names
    would parse as an object and mean nothing.
    """
    by_kind: dict[str, dict] = {}
    for signal in bundle.packet.payload.document_work_signals:
        located = signal.locator.model_dump(mode="json")
        by_kind.setdefault(str(located["kind"]), located)
    assert {"docx", "pptx", "pdf", "spreadsheet", "notebook", "html"} <= by_kind.keys()

    # Each locator parsed into its own model rather than a bag of keys, so the
    # discriminated union has already refused any shape it does not name. What
    # is asserted here is that the *right* one was selected and carries real
    # coordinates rather than a defaulted zero.
    assert by_kind["docx"]["part"]
    assert by_kind["docx"]["block_index"] >= 0
    assert by_kind["pptx"]["slide_number"] >= 1
    assert by_kind["pptx"]["part"]
    assert by_kind["pdf"]["page_number"] >= 1
    assert by_kind["spreadsheet"]["sheet"]
    assert by_kind["spreadsheet"]["cell_or_range"]
    assert by_kind["notebook"]["cell_type"]
    assert by_kind["html"]["node_path"]


def test_no_line_locator_is_claimed_for_a_format_without_lines(bundle) -> None:
    """A line number into a DOCX indexes a derived string, not the document."""
    line_bearing = {"text", "markdown", "csv", "html", "ipynb"}
    for signal in bundle.packet.payload.document_work_signals:
        if signal.locator.kind == "line":
            assert signal.document_format in line_bearing, signal.signal_id


def test_a_pair_score_survives_as_a_number(bundle) -> None:
    """Scores are the reason floats had to cross this boundary at all.

    The producer's canonical renderer refused non-integer numbers, so no score
    could be written; the two runtimes then format the same double differently
    where one leaves decimal notation and the other has not, and a score of
    exactly 1 — what a categorical signal carries when it fires — renders as `1`
    in one and `1.0` in the other.
    """
    scores = [
        score.score
        for relation in bundle.packet.payload.semantic_pair_relations
        for score in relation.method_scores
    ]
    assert scores, "no pair carried a method score"
    assert all(0.0 <= score <= 1.0 for score in scores)
    # At least one score that is not an integer, and at least one that is: both
    # formatting cases have to be present or the fixture proves only the easy one.
    assert any(score != int(score) for score in scores)
    assert any(score == int(score) for score in scores)


def test_an_edited_byte_fails_the_load_rather_than_changing_the_meaning(
    tmp_path: Path, bundle
) -> None:
    """The bundle is bound by hash, so it cannot be quietly adjusted.

    Worth asserting because the fixture is checked-in JSON, and checked-in JSON
    invites exactly the small hand-edit this refuses.
    """
    import shutil

    copy = tmp_path / "corpus-intelligence"
    shutil.copytree(BUNDLE, copy)
    target = copy / bundle.packet.payload_refs["topic_candidates"]
    document = json.loads(target.read_text(encoding="utf-8"))
    document[0]["confidence_class"] = "strong"
    target.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PacketLoadError):
        load_corpus_intelligence_bundle(copy)

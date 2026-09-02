"""A fixture must say what produced it, and the label must stay true.

Two of the three Repository Model fixtures this repository compiles against are
the output of its own legacy scanner at contract 1.0.0, not of the real producer
at 1.1.0. Nothing said so. A suite passing against them reads as "the pipeline
handles Repository Model Packets", when what it establishes is "the pipeline
handles packets this repository wrote for itself" — a materially weaker claim,
and one nobody could have noticed from the test names.

Labelling alone rots: a regenerated fixture and an unchanged PROVENANCE.md is a
label that lies, which is worse than no label. So the label is checked against
the packet it describes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKET_FIXTURES = ROOT / "tests/fixtures/repository_model_packets"

#: The producer of record. A fixture from anything else has to say so.
CURRENT_PRODUCER = "l9-meta-injector.repository-model"


def _fixtures() -> list[Path]:
    return sorted(path for path in PACKET_FIXTURES.iterdir() if (path / "packet.json").is_file())


@pytest.mark.parametrize("fixture", _fixtures(), ids=lambda path: path.name)
def test_every_packet_fixture_records_its_provenance(fixture: Path) -> None:
    provenance = fixture / "PROVENANCE.md"
    packet = json.loads((fixture / "packet.json").read_text(encoding="utf-8"))
    producer = packet["producer"]["name"]
    if producer == CURRENT_PRODUCER:
        # A fixture from the real producer needs no disclaimer; it is the case
        # a reader assumes. Requiring a file here would be ceremony.
        return
    assert provenance.is_file(), (
        f"{fixture.name} was produced by {producer}, not {CURRENT_PRODUCER}, "
        "and carries no PROVENANCE.md saying so"
    )


@pytest.mark.parametrize("fixture", _fixtures(), ids=lambda path: path.name)
def test_a_provenance_label_matches_the_packet_it_describes(fixture: Path) -> None:
    """The check that stops the label drifting away from the bytes."""
    provenance = fixture / "PROVENANCE.md"
    if not provenance.is_file():
        pytest.skip("no provenance file; covered by the test above")
    text = provenance.read_text(encoding="utf-8")
    packet = json.loads((fixture / "packet.json").read_text(encoding="utf-8"))

    assert packet["producer"]["name"] in text, "provenance names a different producer"
    assert packet["producer"]["version"] in text, "provenance names a different producer version"
    # The contract version, matched as a whole token so 1.0.0 is not found
    # inside 1.1.0 or inside a profile version that happens to read the same.
    assert re.search(rf"\*\*{re.escape(packet['packet_version'])}\*\*", text), (
        "provenance does not state the packet contract version in bold, "
        "which is the field a reader is most likely to assume rather than check"
    )


def test_at_least_one_fixture_comes_from_the_current_producer() -> None:
    """Labelling the legacy ones is only half the answer.

    Saying "this is not the real producer" on every fixture would leave the real
    producer qualified by nothing at all. This asserts the other half exists.
    """
    producers = {
        json.loads((fixture / "packet.json").read_text(encoding="utf-8"))["producer"]["name"]
        for fixture in _fixtures()
    }
    assert CURRENT_PRODUCER in producers


def test_the_producer_emitted_corpus_fixture_carries_current_contract_packets() -> None:
    """The strongest producer qualification here, and where to find it."""
    roots = ROOT / "tests/fixtures/corpus_intelligence/producer-emitted/roots"
    packets = sorted(roots.glob("*/packet.json"))
    assert len(packets) >= 2
    for path in packets:
        packet = json.loads(path.read_text(encoding="utf-8"))
        assert packet["producer"]["name"] == CURRENT_PRODUCER
        assert packet["packet_version"] == "1.1.0"

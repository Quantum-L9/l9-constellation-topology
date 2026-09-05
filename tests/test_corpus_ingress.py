"""A canonical packet present is a canonical packet used.

The failure this guards against is specific and quiet: a generation publishes an
``l9.corpus-intelligence`` bundle, the bundle does not verify, and the compiler
reconstructs its own packet from the file layout instead. The compile then
succeeds, reporting topology derived from a second opinion about a run whose own
producer's statement about it was broken — and nothing in the output says so.

So the choice is made on *presence*, never on success. These tests assert that
distinction from both sides: a valid bundle is preferred, an invalid one raises
rather than falling back, and the adapter is reached only where there is no
bundle to prefer.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from l9_constellation_topology.packets.corpus_ingress import (
    CORPUS_INTELLIGENCE_DIRECTORY,
    SOURCE_ADAPTED,
    SOURCE_CANONICAL,
    CorpusIngressError,
    canonical_bundle_path,
    load_corpus_intelligence,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures/corpus_intelligence/producer-emitted"


@pytest.fixture
def generation(tmp_path: Path) -> Path:
    """A copy of the producer-emitted fixture, safe to corrupt."""
    root = tmp_path / "generation"
    shutil.copytree(FIXTURE, root)
    return root


def test_a_published_bundle_is_the_input(generation: Path) -> None:
    ingress = load_corpus_intelligence(generation)
    assert ingress.source == SOURCE_CANONICAL
    assert ingress.is_canonical
    # The adapter records which contract it read a layout under. A canonical
    # ingress read no layout, so claiming a mode would be claiming to have.
    assert ingress.adaptation_mode == ""
    assert len(ingress.root_bundles) == 5


def test_a_corrupted_bundle_raises_rather_than_falling_back(generation: Path) -> None:
    """The case the module exists for.

    The generation is otherwise intact, so the adapter would happily produce a
    packet from it. That is exactly what must not happen.
    """
    target = generation / CORPUS_INTELLIGENCE_DIRECTORY / "payload/topic-candidates.json"
    document = json.loads(target.read_text(encoding="utf-8"))
    document.append(dict(document[0], candidate_id="candidate:injected"))
    target.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(CorpusIngressError) as raised:
        load_corpus_intelligence(generation)
    # The message has to say what to do about it, because the tempting fix is
    # to delete the bundle and let the adapter run.
    assert "does not load" in str(raised.value)
    assert "Refusing to adapt" in str(raised.value)


def test_a_truncated_bundle_raises_too(generation: Path) -> None:
    """A payload file removed is not a payload domain that found nothing."""
    (generation / CORPUS_INTELLIGENCE_DIRECTORY / "payload/readiness-evidence.json").unlink()
    with pytest.raises(CorpusIngressError):
        load_corpus_intelligence(generation)


def test_an_empty_bundle_directory_raises(generation: Path) -> None:
    """Presence is a directory, so an empty one must not read as absence.

    Otherwise the fallback returns through the back door: delete the files,
    keep the directory, and the adapter runs again.
    """
    bundle = generation / CORPUS_INTELLIGENCE_DIRECTORY
    shutil.rmtree(bundle)
    bundle.mkdir()
    assert canonical_bundle_path(generation) == bundle
    with pytest.raises(CorpusIngressError):
        load_corpus_intelligence(generation)


def test_a_generation_without_a_bundle_reaches_the_adapter(generation: Path) -> None:
    """The one case the compatibility path is still for."""
    shutil.rmtree(generation / CORPUS_INTELLIGENCE_DIRECTORY)
    assert canonical_bundle_path(generation) is None
    # This fixture is a bundle beside root packets rather than a full Meta
    # generation, so the adapter cannot read it — which is the right failure and
    # a different one: it is the adapter's own error, not a refusal to reach it.
    # Intentionally broad: the adapter's own error class (not CorpusIngressError).
    # We verify the specific non-type rather than a fixed exception class (S5958: documented).
    with pytest.raises(Exception) as raised:  # noqa: PT011 -- intentional; checked below
        load_corpus_intelligence(generation)
    assert not isinstance(raised.value, CorpusIngressError)


def test_the_packet_the_ingress_returns_is_the_one_on_disk(generation: Path) -> None:
    """No re-derivation between loading and returning."""
    declared = json.loads(
        (generation / CORPUS_INTELLIGENCE_DIRECTORY / "packet.json").read_text(encoding="utf-8")
    )
    ingress = load_corpus_intelligence(generation)
    assert ingress.packet.packet_id == declared["packet_id"]
    assert ingress.packet.semantic_hash == declared["semantic_hash"]
    assert ingress.source != SOURCE_ADAPTED

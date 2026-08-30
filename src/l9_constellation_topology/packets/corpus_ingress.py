"""Choose the Corpus Intelligence packet for a corpus generation.

A generation can now arrive two ways, and only one of them is the contract.

The producer emits an ``l9.corpus-intelligence`` bundle beside the generation it
describes: versioned, hash-bound, and validated by its author before it is
written. That is the canonical input. The other way is
:mod:`.adapters.meta_generation`, which reads the generation's file layout and
reconstructs a packet — compatibility ingress written when no producer emitted
one, and which puts the boundary in the wrong repository. A directory layout
carries no version, so a rename upstream reaches this compiler as adapter
breakage rather than as a version mismatch.

This module is the one place that decides between them, and it decides on
presence rather than on success:

**A canonical bundle present is a canonical bundle used.** No fallback, no
preference order, no "try the packet and adapt if it does not work". A bundle
that is present but does not verify is a producer defect, and adapting around it
would replace a loud failure with a quiet second opinion about the same
generation — two packets describing one run, differing in ways nobody would
look for. It raises.

**The adapter runs only where there is nothing to prefer.** A generation from a
producer that predates the packet has no bundle, and reading it through the
adapter is exactly right for as long as such generations exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .corpus_bundle import load_corpus_intelligence_bundle
from .corpus_intelligence import CorpusIntelligencePacket
from .loader import PacketLoadError, RepositoryModelBundle, load_repository_model_bundle

#: Where a producer publishes the bundle inside a generation. Contract, not
#: layout: a consumer looking for the canonical packet looks here.
CORPUS_INTELLIGENCE_DIRECTORY = "corpus-intelligence"

#: How the packet for a generation was obtained.
SOURCE_CANONICAL = "canonical_packet"
SOURCE_ADAPTED = "adapted_generation"


class CorpusIngressError(RuntimeError):
    """Raised when a generation carries a canonical packet that does not load."""


@dataclass(frozen=True)
class CorpusIngress:
    """The packet for one generation, and where it came from."""

    packet: CorpusIntelligencePacket
    generation_root: Path
    #: ``canonical_packet`` or ``adapted_generation``. Never inferred by a
    #: caller from whether a field happens to be populated.
    source: str
    root_bundles: tuple[RepositoryModelBundle, ...] = ()
    #: Populated only for an adapted generation, where it names the contract the
    #: file layout was read under.
    adaptation_mode: str = ""

    @property
    def is_canonical(self) -> bool:
        return self.source == SOURCE_CANONICAL


def canonical_bundle_path(generation_root: Path) -> Path | None:
    """Return the canonical bundle inside a generation, if it published one."""
    candidate = generation_root / CORPUS_INTELLIGENCE_DIRECTORY
    return candidate if candidate.is_dir() else None


def _input_bundles(generation_root: Path) -> tuple[RepositoryModelBundle, ...]:
    """Load the Repository Model bundle each observed root published.

    The packet's identities resolve against these, so a caller validating the
    packet needs them. A root directory that carries no loadable bundle is not
    skipped: the packet names its inputs by packet id, and silently dropping one
    would turn "this packet analyses a root you did not give me" into "this
    packet analyses fewer roots than it says".
    """
    roots = generation_root / "roots"
    if not roots.is_dir():
        return ()
    bundles: list[RepositoryModelBundle] = []
    for entry in sorted(roots.iterdir()):
        if not entry.is_dir():
            continue
        # A generation nests each root's packet under `bundle/`; the fixture
        # layout flattens that. Accept either rather than making the caller know.
        source = entry / "bundle" if (entry / "bundle").is_dir() else entry
        try:
            bundles.append(load_repository_model_bundle(source))
        except PacketLoadError as exc:
            raise CorpusIngressError(f"root bundle at {source} did not load: {exc}") from exc
    return tuple(bundles)


def load_corpus_intelligence(path: Path) -> CorpusIngress:
    """Return the packet for a generation, preferring the canonical bundle.

    Raises :class:`CorpusIngressError` when a canonical bundle is present and
    does not load. That is the whole point of the function: the failure mode it
    exists to prevent is a compile that quietly reconstructs its own packet from
    the file layout after the producer's own packet turned out to be broken.
    """
    # Imported here rather than at module scope: the adapter is compatibility
    # ingress, and this module is the one that decides whether it is reached.
    from .adapters.meta_generation import adapt_meta_generation, resolve_generation_root

    generation_root = resolve_generation_root(path)
    bundle_path = canonical_bundle_path(generation_root)
    if bundle_path is not None:
        try:
            bundle = load_corpus_intelligence_bundle(bundle_path)
        except PacketLoadError as exc:
            raise CorpusIngressError(
                f"{generation_root} publishes a canonical corpus intelligence bundle that "
                f"does not load: {exc}. Refusing to adapt the generation instead: the "
                "producer's packet is the contract, and reconstructing a second one from "
                "the file layout would replace this failure with a quiet disagreement "
                "about the same run."
            ) from exc
        return CorpusIngress(
            packet=bundle.packet,
            generation_root=generation_root,
            source=SOURCE_CANONICAL,
            root_bundles=_input_bundles(generation_root),
        )

    report = adapt_meta_generation(generation_root)
    return CorpusIngress(
        packet=report.packet,
        generation_root=generation_root,
        source=SOURCE_ADAPTED,
        root_bundles=report.root_bundles,
        adaptation_mode=report.adaptation_mode,
    )


__all__ = [
    "CORPUS_INTELLIGENCE_DIRECTORY",
    "SOURCE_ADAPTED",
    "SOURCE_CANONICAL",
    "CorpusIngress",
    "CorpusIngressError",
    "canonical_bundle_path",
    "load_corpus_intelligence",
]

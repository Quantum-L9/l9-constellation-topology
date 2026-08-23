"""Corpus and root records: what a multi-root compile was made of.

A constellation compiled from Repository Model Packets alone has repositories
and nothing above them. A corpus adds one level: several *roots* — a checkout, a
folder on a disk, a ZIP archive — observed together and analysed as one body.

The distinction that matters here is between a root and a repository. They
coincide often enough to be confusing and are not the same thing: a root is
where bytes were read from, and a repository is what the packet decided those
bytes were. One root can produce a packet about no repository at all (a folder
of Word documents), and the identity of a root must survive that.

What never enters either record is where the bytes sat on the machine that read
them. ``/Volumes/OldSSD/plans`` and ``/mnt/backup/plans`` holding identical
content are one root, and a topology whose identity moved when a drive was
remounted would be worthless for exactly the archaeology this domain exists for.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import FrozenModel
from .confidence import ConfidenceAssessment

#: How a root's identity was established.
#:
#: ``declared`` means an operator named this root. ``inferred`` means the
#: producer discovered it — by finding a repository marker, an archive boundary,
#: or a manifest. An inferred identity is a weaker claim about what the root
#: *is*, and topology records the difference rather than flattening it, because
#: an inferred root that turns out to be two roots is a different kind of error
#: from a declared one that was named wrongly.
RootIdentityClass = Literal["declared", "inferred"]


class RootRecord(FrozenModel):
    """One observed root of a corpus."""

    root_id: str = Field(min_length=1)
    identity_class: RootIdentityClass
    source_revision: str
    #: The Repository Model Packet that observed this root.
    repository_model_packet_id: str = Field(min_length=1)
    #: The repository the root's packet is about, when it names one. ``None`` for
    #: a root that is a folder of documents rather than a repository.
    repository_id: str | None = None
    evidence_refs: tuple[str, ...] = ()
    #: Authority is bounded by ``identity_class``: an inferred root never carries
    #: source authority, because nothing declared it to be a root.
    confidence: ConfidenceAssessment


class CorpusRecord(FrozenModel):
    """The corpus a compile analysed, and the analysis identity it carries.

    Two identities, kept apart on purpose. ``corpus_source_snapshot_id`` is about
    the bytes: it moves when a file is added or changed. ``corpus_analysis_id``
    is about the rules: it moves when a threshold, a decoder, or an embedding
    model moves. Collapsing them would make "the corpus changed" and "we changed
    our mind about the corpus" indistinguishable, and every downstream question
    about why a candidate appeared depends on telling those apart.
    """

    corpus_id: str = Field(min_length=1)
    corpus_source_snapshot_id: str = Field(min_length=1)
    corpus_analysis_id: str = Field(min_length=1)
    root_ids: tuple[str, ...] = ()
    #: Identity of the corpus intelligence packet carrying the coverage report.
    #: A reference rather than a copy: coverage lives in one place.
    coverage_ref: str | None = None
    evidence_refs: tuple[str, ...] = ()
    confidence: ConfidenceAssessment

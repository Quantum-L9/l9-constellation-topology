"""The one shape reconciliation reconciles, whatever produced it.

Repository-model assertions and document work signals are read differently — one
from a line span in a text file, the other from a block in a Word document — and
they are *reconciled* identically. That is deliberate and is the whole reason
this type exists.

The alternative would be a second reconciliation path for structured documents,
and the failure it produces is specific: a `.md` plan declaring ``work.status =
WIP`` and a `.docx` plan declaring ``work.status = Complete`` are one subject
with two competing answers. Reconciled by two engines they become two facts in
two collections, each internally consistent, and the contradiction — which is
the single most useful thing a corpus can surface — is reported by neither.

So both producers lower to this, and the engine downstream never learns which
format a claim came from. Where the evidence *points* still differs, and that
difference is preserved in the evidence record's locator rather than here: a
claim is a claim regardless of whether its proof is a line or a slide.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticInput:
    """One producer statement, reduced to what reconciliation actually reads.

    Everything specific to how the statement was found — the source path, the
    line span or structured locator, the excerpt, the extractor, the decoder — is
    absent by construction. All of it lives on the evidence record built at the
    packet boundary, which is where it belongs: reconciliation decides what
    several answers to one question *mean*, and none of those fields bear on that
    question.
    """

    #: Producer-assigned, content-addressed identity of the statement. The key
    #: that links this input back to the evidence record built for it.
    input_id: str
    subject_id: str
    predicate: str
    object: str
    #: Producer authority vocabulary, mapped conservatively downstream and never
    #: upgraded.
    authority: str
    #: Producer confidence vocabulary.
    confidence: str
    #: ``declared`` for prose or a manifest; ``observed`` for something an
    #: extractor read out of structure.
    evidence_class: str
    #: Where this came from, for diagnostics only. Never an input to arity,
    #: conflict detection, or projection — a conflict must be decided by what the
    #: statements say, not by which producer said them.
    origin: str = "repository-model"

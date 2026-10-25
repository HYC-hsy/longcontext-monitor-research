# Adapted from eea/rag-facts-check b78a082; see REUSE.md and RAG_LICENSE.
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class Span:
    """Character offset span within a text.

    Attributes:
        start: Start character offset (inclusive).
        end: End character offset (exclusive).
    """

    start: int
    end: int

@dataclass
class EvidenceSpan:
    """A verbatim evidence quote located in a source document.

    Attributes:
        quote: The verbatim quote as returned by the judge.
        start: Start character offset (inclusive) within the source document.
        end: End character offset (exclusive) within the source document.
        document_index: 0-based index of the source document the span was
            found in, or None if the quote could not be located.
    """

    quote: str
    start: int
    end: int
    document_index: int | None = None

    def to_dict(self) -> dict:
        """Convert to a dictionary for JSON serialization."""
        return {
            "quote": self.quote,
            "start": self.start,
            "end": self.end,
            "document_index": self.document_index,
        }

@dataclass
class Claim:
    """A single factual claim extracted from a RAG-generated answer.

    Attributes:
        text: The claim text (may be rephrased for clarity).
        index: The 1-based index of the claim in the original answer.
        original_text: Exact verbatim fragment from the answer (for span matching).
        span: Character offsets of the claim in the original answer.
    """

    text: str
    index: int
    original_text: str = ""
    span: Span | None = None

@dataclass
class VerificationResult:
    """Result of verifying a single claim against source documents.

    Attributes:
        claim: The claim text that was verified.
        claim_index: The index of the claim.
        verdict: One of "supported", "contradicted", "not_enough_info".
        confidence: Confidence score 0-100.
        evidence: Verbatim quotes from the source documents (empty list when the
            judge found no evidence). A judge that returns a single string is
            coerced to a one-element list.
        explanation: Brief explanation of the reasoning.
        document_id: ID of the source document containing the evidence (if available).
        document_index: 0-based index of the source document containing the first
            evidence quote (as identified by the judge, or corrected by span
            matching). Used for targeted evidence span matching.
        chunk_id: ID of the document chunk containing the evidence (if available).
        consistency_score: Agreement across multiple verification runs (0-1, for self-consistency).
        evidence_spans: Located spans for the quotes that were actually found in the
            source documents. May be shorter than ``evidence`` when a quote could
            not be matched, and each span carries its own document index.
    """

    claim: str
    claim_index: int
    verdict: str  # "supported" | "contradicted" | "not_enough_info"
    confidence: int  # 0-100
    explanation: str = ""
    evidence: list[str] = field(default_factory=list)
    document_id: str | None = None
    document_index: int | None = None
    chunk_id: str | None = None
    consistency_score: float | None = None
    evidence_spans: list[EvidenceSpan] = field(default_factory=list)

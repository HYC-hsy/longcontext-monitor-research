# Copied from aberaio/sourcecheck d81493d; see SOURCECHECK_LICENSE.
from enum import Enum

class Verdict(str, Enum):
    """The outcome of verifying one claim against its source.

    NOT_VERIFIABLE is a first-class, honest outcome, not a failure. It is the
    verdict whenever the tool cannot confirm support (unresolved citation,
    unretrievable source, or grounding below threshold). Precision first:
    sourcecheck never returns SUPPORTED unless it can show why.
    """

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    NOT_VERIFIABLE = "not_verifiable"

class ReasonCode(str, Enum):
    """Machine-readable explanation of a verdict, so a NOT_VERIFIABLE caused by
    an unresolved citation is distinguishable from one caused by weak grounding
    or an unretrievable source. (Operational network failures are surfaced via
    the ``sourcecheck`` logger, not swallowed silently.)"""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNRESOLVED = "unresolved"           # citation did not resolve to a real source
    RETRACTED = "retracted"             # resolved, but the work has been retracted
    NO_CONTENT = "no_content"           # resolved, but no checkable text (no abstract)
    NO_GROUNDING = "no_grounding"       # content present, but no grounding check ran
    LOW_GROUNDING = "low_grounding"     # grounding ran but stayed below threshold

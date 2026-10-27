"""Pure explicit prompt strategies; no datasets, labels, profiles or runtime calls."""
import copy
from .citation_inputs import identity
from .inputs import require

BASELINE = 'baseline-a'
CANDIDATE = 'semantic-paraphrase-role-clarity-v1'
ONE_SENTENCE = 'semantic-support-one-sentence-v1'
SUPPORT_SENTENCE = 'Assess support by meaning rather than wording, without broadening scope, dropping conditions, or strengthening the claims supported by the evidence.'
BASELINE_CODE = 'ae31a01fb94535d7fb11bbd8b7adfdb639bdb446'
CLARIFICATION = '''Literal quotation matching and host identity checks apply to the submitted
quotations and their recorded sources, not to whether the operation's conclusion repeats
the quotation word for word. Judge semantic support for the conclusion. A paraphrase or
editorial framing is acceptable when it preserves substantive meaning, normative force,
necessity, scope, conditions, negation and quantifiers. Differences in articles or purely
organizational wording alone are not missing evidence; added factual commitments,
priority or obligations, broader scope or omitted restrictions still require support. Identity fields
and content hashes identify the text under review; they are not additional factual claims
that the quotations must prove.
Apply the same source-role discipline to your explanation as to your verdict. Describe
only what the cited material establishes: requirements as requirements, commands as
specified or attempted actions, source code as static behavior, and observed receipts as
reported observations. Do not narrate an action as successfully executed merely because
its command is present, or describe a string in source code as an observed outcome.
Static code may establish narrow properties by inspection without execution tests. Where
an execution outcome or broader conclusion lacks evidence, state that limit without
inventing failure or importing unquoted context.
'''


def apply_strategy(request, strategy=BASELINE):
    require(strategy in (BASELINE,CANDIDATE,ONE_SENTENCE), 'experiment_strategy')
    request=copy.deepcopy(request)
    if strategy==CANDIDATE:
        anchor='Return only one JSON object with exactly op_index, verdict, explanation.'
        require(request['system'].count(anchor)==1, 'candidate_system_anchor')
        request['system']=request['system'].replace(anchor,CLARIFICATION+anchor,1)
    elif strategy==ONE_SENTENCE:
        anchor='SUPPORTED means the submitted quotes suffice'
        require(request['system'].count(anchor)==1, 'one_sentence_system_anchor')
        request['system']=request['system'].replace(anchor,SUPPORT_SENTENCE+'\n'+anchor,1)
    if strategy!=BASELINE:
        request['review_strategy']=strategy
        request['audit_request_sha256']=identity({k:request[k] for k in ('system','prompt','tools')})
    return request

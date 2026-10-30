"""Small shared opt-in contract; no imports of clients, profiles or benchmark data."""
MODES=('gate-only','gate-one-repair')
STRATEGY='semantic-support-one-sentence-v1'
CLAIM_SPLIT='claim-split-same-evidence-v2'
CLAIM_SPLIT_SIMPLE='claim-split-same-evidence-v3'
CLAIM_SPLIT_SEMANTIC='claim-split-same-evidence-v4'
STRATEGIES=(STRATEGY,CLAIM_SPLIT,CLAIM_SPLIT_SIMPLE,CLAIM_SPLIT_SEMANTIC)


def validate_strategy(mode,strategy=None):
    if strategy is not None and (mode is None or strategy not in STRATEGIES):
        raise ValueError('citation review strategy requires an explicit gate and valid strategy')
    return STRATEGY if strategy is None else strategy


def require_strategy_binding(strategy,config,mode):
    effective=validate_strategy(mode,strategy)
    if effective!=validate_strategy(config.get('citation_review_gate'),config.get('citation_review_strategy')):
        raise ValueError('citation review strategy differs from frozen manifest')
    return effective


def validate_gate(mode,candidate,condition='B'):
    if mode is not None and (mode not in MODES or candidate!='pma_gap_evidence_v1' or condition!='B'):
        raise ValueError('citation gate requires explicit evidence PMA B carrier and valid mode')
    return mode


def worker_flags(mode,candidate,strategy=None):
    validate_gate(mode,candidate)
    validate_strategy(mode,strategy)
    flags=['--citation-review-gate',mode] if mode is not None else []
    return flags+(['--citation-review-strategy',strategy] if strategy is not None else [])


def require_gate_binding(mode,config,candidate,condition='B'):
    validate_gate(mode,candidate,condition)
    if mode!=config.get('citation_review_gate'):
        raise ValueError('citation gate differs from frozen manifest')
    return mode


def gate_source_paths():
    from pathlib import Path
    stage=Path(__file__).resolve().parent
    root=stage.parents[2]
    review=root/'pma_evidence_review'
    vendor=[review/'vendor'/name for name in ('rag_models.py','rag_prompts.py','sourcecheck_types.py','rag_span_union.py')]
    vendor+=sorted((review/'vendor/prompts').glob('*.txt'))
    return [p.relative_to(root).as_posix() for p in sorted(review.glob('*.py'))+vendor]+[
        (stage/name).relative_to(root).as_posix() for name in ('citation_gate_agent.py','citation_gate_config.py')]


def verify_gate_sources(config):
    validate_strategy(config.get('citation_review_gate'),config.get('citation_review_strategy'))
    if config.get('citation_review_gate') is None:
        if config.get('citation_gate_source_sha256') is not None:raise ValueError('gate source binding without gate')
        return
    from pathlib import Path
    import hashlib
    root=Path(__file__).resolve().parent.parents[2]
    actual={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in gate_source_paths()}
    if config.get('citation_gate_source_sha256')!=actual:
        raise ValueError('citation gate source identity differs from manifest')

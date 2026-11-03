"""Small shared opt-in contract; no imports of clients, profiles or benchmark data."""
MAINTENANCE_POLICY='maintain-scoped-latest-no-review-v1'
BANK_DISPLAY_POLICY='pma-bank-display-v1'
REQUIREMENT_REMINDER_POLICY='pma-requirement-reminder-v1'
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


def worker_flags(mode,candidate,strategy=None,maintenance_policy=None):
    validate_maintenance(maintenance_policy,candidate,mode,strategy)
    validate_gate(mode,candidate)
    validate_strategy(mode,strategy)
    flags=['--citation-review-gate',mode] if mode is not None else []
    flags += ['--memory-maintenance-policy',maintenance_policy] if maintenance_policy is not None else []
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
        (stage/name).relative_to(root).as_posix() for name in
        ('citation_gate_agent.py','citation_gate_config.py','verbatim_selection_agent.py',
         'tag_selection_contract.py','selection_context.py','verbatim_selection_mixin.py')]+[
        (review/'verbatim_selection_prototype_20261031/contract.py').relative_to(root).as_posix()]


def validate_maintenance(policy,candidate,mode=None,strategy=None,condition='B'):
    carriers = {MAINTENANCE_POLICY: 'pma_gap_evidence_v1',
                BANK_DISPLAY_POLICY: 'pma_gap_memory_v0',
                REQUIREMENT_REMINDER_POLICY: 'pma_gap_memory_v0'}
    if policy is not None and (policy not in carriers or
            candidate != carriers[policy] or condition != 'B' or
            mode is not None or strategy is not None):
        raise ValueError('maintenance policy requires its explicit PMA B carrier without review gate or strategy')
    return policy


def require_maintenance_binding(policy,config,candidate,condition='B'):
    validate_maintenance(policy,candidate,config.get('citation_review_gate'),
                         config.get('citation_review_strategy'),condition)
    if policy != config.get('memory_maintenance_policy'):
        raise ValueError('maintenance policy differs from frozen manifest')
    return policy


def maintenance_source_paths(policy=MAINTENANCE_POLICY):
    from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run_certification import EVIDENCE_GAP_SOURCE_FILES, GAP_SOURCE_FILES
    if policy == REQUIREMENT_REMINDER_POLICY:
        from pathlib import Path
        stage=Path(__file__).resolve().parent
        root=stage.parents[2]
        names=('bank_display_agent.py','selection_context.py','p1_source_archive.py',
            'p1_source_agent.py','p1_source_links.py','p1_linked_agent.py',
            'p1_context_history.py','p1_context_agent.py','p1_requirements.py',
            'p1_requirement_agent.py','p2_requirement_view.py',
            'p2_requirement_agent.py','p2_requirement_reminder.py')
        return list(dict.fromkeys(list(GAP_SOURCE_FILES)+[
            (stage/name).relative_to(root).as_posix() for name in names]))
    return list(GAP_SOURCE_FILES if policy == BANK_DISPLAY_POLICY else EVIDENCE_GAP_SOURCE_FILES)


def verify_gate_sources(config):
    policy=config.get('memory_maintenance_policy')
    validate_maintenance(policy,config.get('research_candidate'),
                         config.get('citation_review_gate'),config.get('citation_review_strategy'))
    if policy is not None:
        from pathlib import Path
        import hashlib
        root=Path(__file__).resolve().parent.parents[2]
        actual={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in maintenance_source_paths(policy)}
        if config.get('maintenance_source_sha256')!=actual:
            raise ValueError('maintenance source identity differs from manifest')
    elif config.get('maintenance_source_sha256') is not None:
        raise ValueError('maintenance source binding without policy')
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

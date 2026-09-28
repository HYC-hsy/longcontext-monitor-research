"""Opt-in strategy adapter; never substitutes the native M1 contract."""

def apply_strategy(agent, policy=None):
    if policy is None:
        return agent
    if not agent.dcec_enabled or not agent.semantic_continuity:
        raise ValueError('strategy requires native DCEC-v1 initialization')
    if policy in agent.system_prompt:
        raise ValueError('strategy already installed')
    agent.system_prompt += '\n\n' + policy
    return agent

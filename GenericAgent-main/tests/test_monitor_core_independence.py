import ast
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = PROJECT_ROOT / "monitor_agent_core"
FORBIDDEN_ROOTS = {
    "agent_loop",
    "agentmain",
    "experiment_conditions",
    "ga",
    "launch",
    "llmcore",
    "mykey",
    "reflect",
    "research_runtime",
    "simphtml",
    "TMWebDriver",
}


def imported_roots(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_monitor_core_has_no_generic_agent_source_dependencies():
    violations = {}
    for path in CORE_ROOT.rglob("*.py"):
        forbidden = imported_roots(path) & FORBIDDEN_ROOTS
        if forbidden:
            violations[path.name] = sorted(forbidden)
    assert violations == {}


def test_importing_monitor_core_does_not_load_generic_agent_modules():
    script = (
        "import json, sys; import monitor_agent_core; "
        f"blocked={FORBIDDEN_ROOTS!r}; "
        "print(json.dumps(sorted(blocked.intersection(sys.modules))))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "[]"


def test_ga_specific_conversion_stays_outside_monitor_core():
    adapter = (PROJECT_ROOT / "ga_monitor_adapter.py").read_text(encoding="utf-8")
    assert "from research_runtime import CompletionDecision" in adapter
    assert not (CORE_ROOT / "ga_monitor_adapter.py").exists()

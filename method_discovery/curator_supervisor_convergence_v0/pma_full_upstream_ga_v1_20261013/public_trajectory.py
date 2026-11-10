"""Load the shared, dependency-free protocol without importing the GA runtime."""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[3] / "GenericAgent-main/task_trajectory.py"
_spec = importlib.util.spec_from_file_location("_public_task_trajectory_protocol", _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
batch_rounds = _module.batch_rounds
validate_trajectory = _module.validate_trajectory
format_trajectory = _module.format_trajectory
SCHEMA = _module.SCHEMA

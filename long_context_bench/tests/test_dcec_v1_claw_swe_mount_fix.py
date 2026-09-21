from pathlib import Path

import pytest

from method_discovery.run_dcec_v1_claw_swe_generalization import (
    prepare_source_snapshot_mountpoints,
)


def test_materializes_only_missing_temp_nested_mountpoint(tmp_path: Path) -> None:
    snapshot = tmp_path / "source"
    memory = snapshot / "memory"
    memory.mkdir(parents=True)
    marker = memory / "existing.txt"
    marker.write_text("keep", encoding="utf-8")

    result = prepare_source_snapshot_mountpoints(snapshot)

    assert Path(result["temp"]) == snapshot / "temp"
    assert (snapshot / "temp").is_dir()
    assert Path(result["memory"]) == memory
    assert marker.read_text(encoding="utf-8") == "keep"


def test_rejects_snapshot_without_required_memory_mountpoint(tmp_path: Path) -> None:
    snapshot = tmp_path / "source"
    snapshot.mkdir()

    with pytest.raises(RuntimeError, match="missing memory"):
        prepare_source_snapshot_mountpoints(snapshot)

    assert not (snapshot / "temp").exists()

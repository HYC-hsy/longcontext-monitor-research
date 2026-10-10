"""Research-only identity gates for the C02 native-boundary comparison."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.diagnostic_history_projection_v1_20261010.projection import HERE as SOURCE_DIR
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.adapter import canonical


HERE = Path(__file__).resolve().parent
OLD = ("这是固定截止快照上的诊断。Task 不再推进；历史工具会话不代表仍有活动进程。"
       "可以调查允许的公开材料。wait、intervene、allow_complete 在此只记录诊断提议并结束当前诊断，"
       "不会等待 Task 新反馈、向 Task 投递消息或执行真实完成放行。")
NEW = ("这是固定截止快照上的诊断。Task 不再推进；历史工具会话不代表仍有活动进程。"
       "可以调查允许的公开材料。wait、intervene、allow_complete 按现有控制流程处理；"
       "调用可能返回错误或要求继续复审，并不保证立即结束诊断。"
       "仅在控制流程最终选择干预或允许完成时记录研究终点；"
       "不会等待 Task 新反馈、向 Task 投递消息或执行真实完成放行。")
EXPECTED = {
    "H": "d4a866f07c8376fd990745dda4d207b87299e7d690117c7584dcf2b28f1fa77b",
    "R": "58ad93e929c086c78ef5e7094d715481c584bf69f86f1af415c4ebb91b330e56",
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build_requests() -> tuple[dict[str, dict], dict]:
    result, identity = {}, {}
    for arm, count in (("H", 96), ("R", 9)):
        path = SOURCE_DIR / "frozen_requests" / f"{arm}_REQUEST.json"
        raw = path.read_bytes()
        source = json.loads(raw)
        if len(source["messages"]) != count or source["system"].count(OLD) != 1:
            raise RuntimeError(f"{arm} source request or footer identity changed")
        if not source["system"].endswith("\n\n" + OLD):
            raise RuntimeError(f"{arm} old footer is not the unique terminal segment")
        target = copy.deepcopy(source)
        target["system"] = source["system"][:-len(OLD)] + NEW
        if digest(canonical(target)) != EXPECTED[arm]:
            raise RuntimeError(f"{arm} full request canonical identity mismatch")
        if any(target[key] != source[key] for key in source if key != "system"):
            raise RuntimeError(f"{arm} non-system source field changed")
        result[arm] = target
        identity[arm] = {"source_raw_sha256": digest(raw),
                         "source_canonical_sha256": digest(canonical(source)),
                         "full_canonical_sha256": digest(canonical(target)),
                         "message_count": count}
    if (result["H"]["system"] != result["R"]["system"] or
            any(result["H"][key] != result["R"][key]
                for key in result["H"] if key not in {"system", "messages"}) or
            result["H"]["messages"][88:] != result["R"]["messages"][1:]):
        raise RuntimeError("H/R common context or native tail differs")
    return result, identity


def write_frozen_requests():
    requests, identity = build_requests()
    target = HERE / "frozen_requests"
    target.mkdir(exist_ok=True)
    for arm, payload in requests.items():
        source = SOURCE_DIR / "frozen_requests" / f"{arm}_REQUEST.json"
        source_copy = target / f"{arm}_SOURCE_REQUEST.json"
        if source_copy.exists() and source_copy.read_bytes() != source.read_bytes():
            raise RuntimeError(f"Frozen {arm} source copy changed")
        if not source_copy.exists():
            source_copy.write_bytes(source.read_bytes())
        path = target / f"{arm}_FULL_REQUEST.json"
        if path.exists() and json.loads(path.read_text(encoding="utf-8")) != payload:
            raise RuntimeError(f"Frozen {arm} full request already exists with different bytes")
        if not path.exists():
            path.write_bytes(canonical(payload))
    manifest = {"footer_old_utf8_sha256": digest(OLD.encode()),
                "footer_new_utf8_sha256": digest(NEW.encode()),
                "only_common_change": "terminal system footer replacement after two LF",
                "requests": identity}
    path = target / "REQUEST_IDENTITY.json"
    if path.exists() and json.loads(path.read_text(encoding="utf-8")) != manifest:
        raise RuntimeError("Frozen request identity manifest differs")
    if not path.exists():
        path.write_bytes(canonical(manifest))
    return manifest


if __name__ == "__main__":
    write_frozen_requests()

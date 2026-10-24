"""Deterministic text-projection contracts, no model or evaluator calls."""
import json
from types import SimpleNamespace as NS
import unittest

from evidence_gap_context import event_identity, prepare_context
from gap_evidence import (RenderBlock, SourceRegistry, SourceScopeError,
                          bind_evidence, excerpt, register_public_source,
                          render_source_blocks)


class ProjectionRepairTests(unittest.TestCase):
    def project(self, content, commands=()):
        captured = []
        identity = event_identity(dict(event_id="event-2", sequence=2,
                                       kind="actor_step", response="report"))
        entry = dict(analysis="report", commands=list(commands),
            observation=json.dumps({"content": "report", "tool_results": [
                {"tool_use_id": "call-1", "content": content}]}),
            _evidence_identity=identity)
        wrapper = NS(_memory_agent=NS(prepare_visible_context=lambda raw, blocks:
                         captured.append((raw, blocks))),
            _get_memory_agent_context=lambda: "unchanged P2 query",
            _task_description="task", _evidence_task_identity=event_identity(
                dict(event_id="event-1", sequence=1, kind="task_start")),
            _sliding_window_size=1, _accumulated_observations=[{}, entry])
        prepare_context(wrapper)
        self.assertEqual(captured[0][0], "unchanged P2 query")
        return captured[0][1]

    def render(self, blocks):
        registry, rendered, parents = SourceRegistry("fixture"), [], {}
        for b in blocks:
            parent = parents.get((b["source_id"], b.get("parent_field_path")))
            _, row = register_public_source(registry, event_id=b["source_id"],
                role=b["role"], text=b["text"], order=b["order"],
                field_path=b["field_path"], record_digest=b["record_digest"],
                record_digest_kind=b["record_digest_kind"],
                parent_wrapper_source_id=parent, tool_call_id=b.get("tool_call_id"))
            parents[b["source_id"], b["field_path"]] = row.source_id
            rendered.append(RenderBlock(registry.snapshot(row.source_id),
                                        b.get("render_spans")))
        return registry, render_source_blocks(rendered, cycle_id="fixture")

    def test_multiline_exact_quote_and_literal_escape_preservation(self):
        body = 'say "hello"\nC:\\new\\test\\file\nregex \\d+\\n\n雪 😀'
        raw = json.dumps(dict(status="success", stdout=body, stderr="warning\nnext",
                              exit_code=7), ensure_ascii=True)
        registry, parts = self.render(self.project(raw))
        stdout = next(v for v in parts.catalog.values()
                      if v.snapshot.record.field_path.endswith("/stdout"))
        self.assertEqual(stdout.snapshot.blob.text, body)
        self.assertIn(body, parts.text)
        self.assertNotIn(json.dumps(body, ensure_ascii=True), parts.text)
        refs = bind_evidence([dict(source=stdout.snapshot.record.handle, quote=body)], parts.catalog)
        self.assertEqual(excerpt(refs[0], {stdout.visibility_ref: stdout}), body)
        parent = stdout.snapshot.parent_wrapper
        self.assertEqual(parent.blob.text, raw)
        self.assertEqual(parent.record.tool_call_id, "call-1")
        self.assertIn('"exit_code": 7', parts.text)
        self.assertIn('"status": "success"', parts.text)
        with self.assertRaises(SourceScopeError):
            bind_evidence([dict(source=parent.record.handle, quote=json.dumps(body))], parts.catalog)
        self.assertEqual(len(registry.sources), 5)

    def test_actual_agent_preparation_retains_parent_and_selected_spans(self):
        from evidence_gap_agent import EvidenceGapMemoryAgent
        agent = object.__new__(EvidenceGapMemoryAgent)
        agent._namespace = "fixture"
        blocks = self.project(json.dumps(dict(status="ok", stdout="a\nb", exit_code=0)))
        agent.prepare_visible_context("unchanged P2 query", blocks)
        _, registry, rendered, error = agent._prepared
        self.assertIsNone(error)
        parts = render_source_blocks(rendered, cycle_id="fixture")
        child = next(v for v in parts.catalog.values()
                     if v.snapshot.record.field_path.endswith("/stdout"))
        self.assertIsNotNone(child.snapshot.parent_wrapper)
        self.assertIn("a\nb", parts.text)
        self.assertNotIn('"a\\nb"', parts.text)
        self.assertEqual(len(registry.sources), 4)

    def test_commands_keep_ids_paths_and_no_result_pairing_guess(self):
        code, body = 'print("雪")\nprint(r"\\n")', 'line one\nline two'
        commands = [json.dumps(dict(tool_name="code_run", args={"script": code,
                    "timeout": 30}, id="different-call")),
                    json.dumps(dict(tool_name="file_write", args={"path": "x.txt",
                    "content": body}, id="write-call"))]
        _, parts = self.render(self.project("plain result", commands))
        for path, expected, call_id in [("commands/0/args/script", code, "different-call"),
                                        ("commands/1/args/content", body, "write-call")]:
            visible = next(v for v in parts.catalog.values() if v.snapshot.record.field_path == path)
            self.assertEqual(visible.snapshot.blob.text, expected)
            self.assertEqual(visible.snapshot.record.tool_call_id, call_id)
            self.assertEqual(visible.snapshot.parent_wrapper.record.tool_call_id, call_id)
            bind_evidence([dict(source=visible.snapshot.record.handle, quote=expected)], parts.catalog)
        self.assertIn('"timeout": 30', parts.text)
        self.assertIn('"path": "x.txt"', parts.text)

    def test_unknown_malformed_nontext_and_empty_stay_literal(self):
        for raw in ['{"status": "ok", "stdout": "broken}',
                    '{"status":"ok","stdout":"x"} trailing',
                    '{"stdout":"line\\nnext"}',
                    '{"status":"ok","stdout":42,"stderr":null,"output":[]}',
                    '{"status":"ok","stdout":"","extra":"a\\nb"}',
                    '{"status":"ok","stdout":"x","stdout":"y"}']:
            with self.subTest(raw=raw):
                blocks = self.project(raw)
                self.assertEqual(blocks[-1]["text"], raw)
                self.assertNotIn("render_spans", blocks[-1])
                self.assertFalse(any("parent_field_path" in b for b in blocks))
        unknown = json.dumps(dict(tool_name="unknown", args={"script":"a\nb"}, id="x"))
        self.assertEqual(self.project("plain", [unknown])[2]["text"], unknown)

    def test_escaped_keys_unicode_and_repeated_projection_are_stable(self):
        raw = '{"status":"ok","std\\u006fut":"雪\\nnext","output":"{\\"stdout\\":\\"still\\\\ntext\\"}"}'
        first, second = self.project(raw), self.project(raw)
        self.assertEqual(first, second)
        _, parts = self.render(first)
        output = next(v for v in parts.catalog.values()
                      if v.snapshot.record.field_path.endswith("/output"))
        self.assertEqual(output.snapshot.blob.text, '{"stdout":"still\\ntext"}')
        self.assertIn('雪\nnext', parts.text)
        command = '{"tool_name":"code_run","args":{"scr\\u0069pt":"a\\nb"},"id":"c"}'
        self.assertTrue(any(b["field_path"] == "commands/0/args/script"
                            for b in self.project("plain", [command])))


if __name__ == "__main__":
    unittest.main()

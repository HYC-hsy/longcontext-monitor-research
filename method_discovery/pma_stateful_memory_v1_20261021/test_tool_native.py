"""Offline native-boundary fixtures, not provider or transport integration."""
import copy
import unittest

from .tool_native import (NativeToolError, normalize_claude_response,
                          validate_tool_arguments)


def call(identifier="toolu_1", name="propose", arguments=None):
    return {"type": "tool_use", "id": identifier, "name": name,
            "input": {} if arguments is None else arguments}


def response(*blocks, stop_reason="tool_use"):
    return {"id": "msg_fixture", "type": "message", "role": "assistant",
            "content": list(blocks), "stop_reason": stop_reason,
            "usage": {"input_tokens": 10, "output_tokens": 12}}


def normalize(value, **kwargs):
    return normalize_claude_response(value, **{
        "permitted_tool_names": frozenset({"propose", "finish"}),
        "response_complete": True, **kwargs})


class NativeBoundaryTests(unittest.TestCase):
    def reject(self, value, code, **kwargs):
        with self.assertRaises(NativeToolError) as caught:
            normalize(value, **kwargs)
        self.assertEqual(caught.exception.code, code)
        self.assertFalse(hasattr(caught.exception, "calls"))
        return caught.exception

    def test_complete_claude_native_batch_and_visible_text(self):
        value = response({"type": "text", "text": "I will propose a change."},
            {"type": "thinking", "thinking": "opaque", "signature": "sig"},
            call(arguments={"a": [1, None, True, {"s": "中文"}]}),
            call("toolu_2", "finish", '{\n "note": "line1\\nline2"\n}'),
            {"type": "text", "text": "after"})
        result = normalize(value)
        self.assertEqual(result["calls"], [
            {"name": "propose", "arguments": {"a": [1, None, True, {"s": "中文"}]}},
            {"name": "finish", "arguments": {"note": "line1\nline2"}}])
        self.assertEqual(result["tool_call_ids"], ["toolu_1", "toolu_2"])
        self.assertEqual(result["visible_text"], "I will propose a change.\nafter")

    def test_output_does_not_alias_input(self):
        value = response(call(arguments={"nested": [{"value": 1}]}))
        original = copy.deepcopy(value)
        result = normalize(value)
        result["calls"][0]["arguments"]["nested"][0]["value"] = 2
        self.assertEqual(value, original)
        value["content"][0]["input"]["nested"].append("new")
        self.assertEqual(len(result["calls"][0]["arguments"]["nested"]), 1)

    def test_no_text_fallback_and_no_implicit_noop(self):
        for text in ['{"name":"finish","arguments":{}}',
                     '<tool_use name="finish">{}</tool_use>',
                     '```json\n{"calls": []}\n```', "I refuse."]:
            error = self.reject(response({"type": "text", "text": text}),
                                "no_native_tool_calls")
            self.assertEqual(error.visible_text, text)
        self.reject(response(), "no_native_tool_calls")

    def test_truncated_missing_and_wrong_end_reject_even_with_valid_call(self):
        for stop in ("max_tokens", "end_turn", "stop_sequence", "pause_turn", None):
            with self.subTest(stop=stop):
                self.reject(response(call(), stop_reason=stop), "invalid_tool_stop_reason")
        value = response(call())
        del value["stop_reason"]
        self.reject(value, "invalid_tool_stop_reason")
        for complete in (False, None, 1, "true"):
            self.reject(response(call()), "response_incomplete", response_complete=complete)
        with self.assertRaises(TypeError):
            normalize_claude_response(response(call()), permitted_tool_names=("propose",))

    def test_standalone_refusal_classification_is_not_substring_detection(self):
        text = {"type": "text", "text": "I cannot discuss that."}
        self.reject(response(text, stop_reason="end_turn"), "model_refusal")
        self.assertEqual(len(normalize(response(text, call()))["calls"]), 1)
        self.assertEqual(len(normalize(response(call(arguments={
            "quote": text["text"]})))["calls"]), 1)
        self.reject(response({"type": "text", "text": "Quoted: " + text["text"]},
                             stop_reason="end_turn"), "invalid_tool_stop_reason")

    def test_decoded_huge_integer_must_be_json_serializable(self):
        import sys
        if not hasattr(sys, "get_int_max_str_digits") or not sys.get_int_max_str_digits():
            self.skipTest("Host does not impose integer serialization limit")
        value = 10 ** (sys.get_int_max_str_digits() + 1)
        self.reject(response(call(arguments={"value": value})), "arguments_not_serializable")

    def test_native_refusals_not_quoted_refusal_text(self):
        for value in (response(call(), {"type": "refusal", "refusal": "No"}),
                      response(call(), stop_reason="refusal"),
                      {**response(call()), "refusal": True},
                      {**response(call()), "refusal": "denied"}):
            self.reject(value, "native_refusal")
        result = normalize(response(call(arguments={"refusal": True,
            "quote": "I refuse to comply", "stop_reason": "max_tokens"})))
        self.assertTrue(result["calls"][0]["arguments"]["refusal"])

    def test_request_names_are_frozen_and_not_inferred_from_response(self):
        self.reject(response(call(name="unrequested")), "unpermitted_tool_name")
        self.reject(response(call()), "tool_names_not_request_frozen",
                    permitted_tool_names={"propose"})
        self.reject(response(call()), "invalid_permitted_tool_names",
                    permitted_tool_names=())
        self.reject(response(call()), "duplicate_permitted_tool_name",
                    permitted_tool_names=("propose", "propose"))
        self.reject(response(call()), "invalid_permitted_tool_names",
                    permitted_tool_names=(True,))
        self.assertEqual(len(normalize(response(call()),
            permitted_tool_names=("propose",))["calls"]), 1)

    def test_mixed_batch_invalidity_is_atomic_and_does_not_mutate(self):
        bad_blocks = [(call("toolu_1"), "duplicate_tool_call_id"),
                      (call("toolu_2", "unknown"), "unpermitted_tool_name"),
                      (call("toolu_2", arguments="[]"), "arguments_not_object"),
                      ({**call("toolu_2"), "extra": True}, "invalid_tool_block_fields")]
        for bad, code in bad_blocks:
            value = response({"type": "text", "text": "archived"}, call(), bad)
            original = copy.deepcopy(value)
            error = self.reject(value, code)
            self.assertEqual(error.visible_text, "archived")
            self.assertEqual(value, original)

    def test_ids_and_tool_block_shape(self):
        for identifier in (None, [], 1, "", "  "):
            self.reject(response(call(identifier)), "invalid_tool_call_id")
        for key in ("id", "input", "name"):
            block = call()
            del block[key]
            self.reject(response(block), "invalid_tool_block_fields")
        self.reject(response(call(name=[])), "unpermitted_tool_name")
        self.reject(response({"type": "server_tool_use", "name": "propose"}),
                    "unsupported_content_block")

    def test_strict_string_json_and_raw_json_compatibility(self):
        cases = [("null", "arguments_not_object"), ("[]", "arguments_not_object"),
                 ('{"x":1,"x":2}', "duplicate_json_key"),
                 ('{"x":{"a":1,"a":2}}', "duplicate_json_key"),
                 ('{"x":NaN}', "nonfinite_json_number"),
                 ('{"x":Infinity}', "nonfinite_json_number"),
                 ('{"x":1e999}', "nonfinite_json_number"),
                 ('{} {}', "invalid_arguments_json"),
                 ('```json\n{}\n```', "invalid_arguments_json"),
                 ('{"x":', "invalid_arguments_json"),
                 ([], "arguments_not_object"), (True, "arguments_not_object"),
                 ({"x": float("nan")}, "nonfinite_json_number"),
                 ({"x": [float("inf")]}, "nonfinite_json_number"),
                 ({"x": (1, 2)}, "non_json_value"),
                 ({1: "value"}, "non_string_json_key"),
                 ({"x": "\ud800"}, "invalid_json_unicode")]
        for arguments, code in cases:
            with self.subTest(arguments=repr(arguments)):
                self.reject(response(call(arguments=arguments)), code)
        block = call()
        block["input"] = None
        self.reject(response(block), "arguments_not_object")
        cycle = {}
        cycle["self"] = cycle
        self.reject(response(call(arguments=cycle)), "cyclic_json_value")

    def test_bad_envelope_and_content_types(self):
        self.reject("native-looking text", "response_not_object")
        self.reject({**response(call()), "role": "user"}, "invalid_message_envelope")
        self.reject({**response(call()), "type": "content_block_delta"},
                    "invalid_message_envelope")
        self.reject({**response(call()), "content": None}, "invalid_content")
        self.reject(response(call(), None), "invalid_content_block")
        self.reject(response(call(), {"type": "text", "text": None}), "invalid_visible_text")


class ArgumentSchemaTests(unittest.TestCase):
    schema = {"type": "object", "properties": {
        "version": {"type": "integer", "minimum": 1},
        "message": {"type": "string", "minLength": 1, "maxLength": 8},
        "refs": {"type": "array", "items": {"type": ["string", "null"]},
                 "maxItems": 2}}, "required": ["version"], "additionalProperties": False}

    def test_valid_and_detached(self):
        value = {"version": 1, "message": "ok", "refs": ["r", None]}
        result = validate_tool_arguments(value, self.schema)
        result["refs"].append("x")
        self.assertEqual(value["refs"], ["r", None])

    def test_fail_closed_parameters(self):
        for value in ({"version": True}, {"version": 1.0}, {"version": 0}, {},
                      {"version": 1, "extra": 1}, {"version": 1, "message": ""},
                      {"version": 1, "refs": [False]},
                      {"version": 1, "refs": ["a", "b", "c"]}):
            with self.subTest(value=value), self.assertRaises(NativeToolError):
                validate_tool_arguments(value, self.schema)

    def test_unknown_schema_keywords_rejected_even_for_absent_property(self):
        schema = copy.deepcopy(self.schema)
        schema["properties"]["message"]["pattern"] = "x"
        with self.assertRaises(NativeToolError) as caught:
            validate_tool_arguments({"version": 1}, schema)
        self.assertEqual(caught.exception.code, "unsupported_argument_schema")

    def test_enum_const_distinguish_bool_from_number_recursively(self):
        for rule in ({"enum": [1]}, {"const": 1},
                     {"enum": [{"nested": [1]}]}):
            value = {"nested": [True]} if type(rule.get("enum", [None])[0]) is dict else True
            with self.assertRaises(NativeToolError):
                validate_tool_arguments({"x": value}, {"type": "object", "properties": {
                    "x": {"type": ["boolean", "integer", "object"], **rule}}})

    def test_all_actual_sibling_definitions_and_valid_fixtures(self):
        from .tool_decisions import audit_tool_definitions, selection_tool_definitions
        from .tool_maintenance import tool_definitions
        from .tool_native import _check_schema
        definitions = audit_tool_definitions() + selection_tool_definitions() + tool_definitions()
        for definition in definitions:
            _check_schema(definition["function"]["parameters"])
        fixtures = {
            "submit_audit": {"outcome": "clean", "issues": [],
                "closure_assessments": [], "unusable_reason": None},
            "submit_selection": {"decision": "silent", "refs": None,
                                 "context_for_action": None},
            "memory_no_change": {},
            "put_entity": {"entity_id": "e1", "entity_type": "file", "display_name": "x"}}
        for definition in definitions:
            function = definition["function"]
            if function["name"] in fixtures:
                value = fixtures[function["name"]]
                self.assertEqual(validate_tool_arguments(value, function["parameters"]), value)

    def test_union_empty_schema_and_absent_type(self):
        schema = {"properties": {"x": {"anyOf": [{"type": "null"},
            {"type": "integer", "minimum": 2}], "enum": [None, 3]}, "free": {}},
            "required": ["x"]}
        self.assertEqual(validate_tool_arguments({"x": 3, "free": [True, None]}, schema),
                         {"x": 3, "free": [True, None]})
        for value in ({"x": True}, {"x": 1}, {"x": 2}, {"x": None, "free": float("nan")},
                      {"x": None, "free": (1,)}, {"x": None, "free": {1: "bad"}}):
            with self.assertRaises(NativeToolError):
                validate_tool_arguments(value, schema)
        for malformed in ({"anyOf": []}, {"anyOf": [{} , {"pattern": "x"}]},
                          {"type": None}):
            with self.assertRaises(NativeToolError):
                validate_tool_arguments({}, malformed)

    def test_nested_additional_properties_schema(self):
        schema = {"type": "object", "additionalProperties": {"type": "integer"}}
        self.assertEqual(validate_tool_arguments({"x": 2}, schema), {"x": 2})
        with self.assertRaises(NativeToolError):
            validate_tool_arguments({"x": True}, schema)


if __name__ == "__main__":
    unittest.main()

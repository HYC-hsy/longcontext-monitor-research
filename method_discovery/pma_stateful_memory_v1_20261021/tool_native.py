"""Pure, fail-closed reference boundary for complete Claude native responses.

Not a provider integration or SSE validator. The host must freeze the permitted
names when sending its request and prove transport completion before setting
response_complete=True. Visible text is returned for host archival only, never
interpreted as a call. This module performs no persistence or external actions.
"""
from __future__ import annotations

import json
import math


class NativeToolError(ValueError):
    """A rejected batch: no executable calls are exposed by this exception."""

    def __init__(self, code: str, visible_text: str = ""):
        self.code = code
        self.visible_text = visible_text
        super().__init__(code)


def _json_copy(value, active=None):
    """Validate and detach JSON data, rejecting Python-only/coercible values."""
    active = set() if active is None else active
    kind = type(value)
    if value is None or kind in (bool, int):
        return value
    if kind is float:
        if not math.isfinite(value):
            raise NativeToolError("nonfinite_json_number")
        return value
    if kind is str:
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise NativeToolError("invalid_json_unicode") from exc
        return value
    if kind not in (dict, list):
        raise NativeToolError("non_json_value")
    if id(value) in active:
        raise NativeToolError("cyclic_json_value")
    active.add(id(value))
    try:
        if kind is list:
            return [_json_copy(item, active) for item in value]
        if any(type(key) is not str for key in value):
            raise NativeToolError("non_string_json_key")
        return {_json_copy(key, active): _json_copy(item, active)
                for key, item in value.items()}
    finally:
        active.remove(id(value))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise NativeToolError("duplicate_json_key")
        result[key] = value
    return result


def _constant(value):
    raise NativeToolError("nonfinite_json_number")


def _arguments(value):
    if type(value) is str:
        try:
            value = json.loads(value, object_pairs_hook=_pairs,
                               parse_constant=_constant)
        except (ValueError, RecursionError) as exc:
            if isinstance(exc, NativeToolError):
                raise
            raise NativeToolError("invalid_arguments_json") from exc
    if type(value) is not dict:
        raise NativeToolError("arguments_not_object")
    detached = _json_copy(value)
    try:
        json.dumps(detached, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise NativeToolError("arguments_not_serializable") from exc
    return detached


def normalize_claude_response(response, *, permitted_tool_names,
                              response_complete: bool) -> dict:
    """Return {calls, tool_call_ids, visible_text}, or reject the entire batch.

    Input is a decoded Claude Messages response, not text, an SDK object, or
    stream deltas. Native tool_use.input may be an object or a strict JSON
    string supplied by an explicit upstream adapter. Unknown content types are
    rejected; supported non-executable thinking blocks are ignored. A completed
    tool-bearing response must end with stop_reason='tool_use'. The completeness
    flag is a caller assertion, not a claim that this function verified SSE.
    """
    text = ""
    try:
        if type(response) is not dict:
            raise NativeToolError("response_not_object")
        content = response.get("content")
        if type(content) is list:
            text = "\n".join(block["text"] for block in content
                if type(block) is dict and block.get("type") == "text"
                and type(block.get("text")) is str)
        if response_complete is not True:
            raise NativeToolError("response_incomplete")
        if response.get("type") != "message" or response.get("role") != "assistant":
            raise NativeToolError("invalid_message_envelope")
        if response.get("refusal") not in (None, False, ""):
            raise NativeToolError("native_refusal")
        if response.get("stop_reason") == "refusal":
            raise NativeToolError("native_refusal")
        if type(content) is not list:
            raise NativeToolError("invalid_content")
        if any(type(block) is dict and block.get("type") == "refusal"
               for block in content):
            raise NativeToolError("native_refusal")
        if (response.get("stop_reason") == "end_turn" and content and
                all(type(block) is dict and block.get("type") == "text"
                    for block in content) and text.strip() == "I cannot discuss that."):
            # Exact standalone refusal classification only; never call extraction.
            raise NativeToolError("model_refusal")
        if response.get("stop_reason") != "tool_use":
            raise NativeToolError("invalid_tool_stop_reason")
        if type(permitted_tool_names) not in (tuple, frozenset):
            raise NativeToolError("tool_names_not_request_frozen")
        if (not permitted_tool_names or any(type(name) is not str or not name
                for name in permitted_tool_names)):
            raise NativeToolError("invalid_permitted_tool_names")
        allowed = frozenset(permitted_tool_names)
        if len(allowed) != len(permitted_tool_names):
            raise NativeToolError("duplicate_permitted_tool_name")
        calls, ids = [], []
        for block in content:
            if type(block) is not dict:
                raise NativeToolError("invalid_content_block")
            kind = block.get("type")
            if kind == "text":
                if type(block.get("text")) is not str:
                    raise NativeToolError("invalid_visible_text")
                _json_copy(block["text"])
                continue
            if kind in ("thinking", "redacted_thinking"):
                # Opaque provider metadata has no executable interpretation.
                _json_copy(block)
                continue
            if kind != "tool_use":
                raise NativeToolError("unsupported_content_block")
            if set(block) != {"type", "id", "name", "input"}:
                raise NativeToolError("invalid_tool_block_fields")
            identifier, name = block["id"], block["name"]
            if type(identifier) is not str or not identifier.strip():
                raise NativeToolError("invalid_tool_call_id")
            _json_copy(identifier)
            if identifier in ids:
                raise NativeToolError("duplicate_tool_call_id")
            if type(name) is not str or name not in allowed:
                raise NativeToolError("unpermitted_tool_name")
            args = _arguments(block["input"])
            ids.append(identifier)
            calls.append({"name": name, "arguments": args})
        if not calls:
            raise NativeToolError("no_native_tool_calls")
        return {"calls": calls, "tool_call_ids": ids, "visible_text": text}
    except (NativeToolError, RecursionError) as exc:
        code = exc.code if isinstance(exc, NativeToolError) else "json_too_deep"
        raise NativeToolError(code, text) from exc


_SCHEMA_KEYS = {"type", "properties", "required", "additionalProperties",
    "items", "enum", "const", "minimum", "maximum", "minLength",
    "maxLength", "minItems", "maxItems", "description", "title", "$comment", "anyOf"}
_TYPES = {"object": dict, "array": list, "string": str, "integer": int,
          "boolean": bool, "null": type(None)}


def _check_schema(schema):
    if type(schema) is not dict or set(schema) - _SCHEMA_KEYS:
        raise NativeToolError("unsupported_argument_schema")
    kinds = schema.get("type")
    kinds = [kinds] if type(kinds) is str else kinds
    if "type" in schema and (type(kinds) is not list or not kinds or
            any(type(kind) is not str or kind not in {*_TYPES, "number"}
                for kind in kinds) or len(set(kinds)) != len(kinds)):
        raise NativeToolError("invalid_argument_schema")
    if "anyOf" in schema:
        alternatives = schema["anyOf"]
        if type(alternatives) is not list or not alternatives:
            raise NativeToolError("invalid_argument_schema")
        for alternative in alternatives:
            _check_schema(alternative)
    for key in ("properties",):
        if key in schema:
            if type(schema[key]) is not dict:
                raise NativeToolError("invalid_argument_schema")
            for child in schema[key].values():
                _check_schema(child)
    if "required" in schema:
        required = schema["required"]
        if (type(required) is not list or any(type(x) is not str for x in required)
                or len(set(required)) != len(required)):
            raise NativeToolError("invalid_argument_schema")
    for key in ("items", "additionalProperties"):
        if key in schema:
            if key == "additionalProperties" and type(schema[key]) is bool:
                continue
            _check_schema(schema[key])
    for key in ("minLength", "maxLength", "minItems", "maxItems"):
        if key in schema and (type(schema[key]) is not int or schema[key] < 0):
            raise NativeToolError("invalid_argument_schema")
    for key in ("minimum", "maximum"):
        if key in schema and type(schema[key]) not in (int, float):
            raise NativeToolError("invalid_argument_schema")
    if "enum" in schema and (type(schema["enum"]) is not list or not schema["enum"]):
        raise NativeToolError("invalid_argument_schema")


def _equal(left, right):
    # JSON equality must not let Python True == 1 satisfy enum/const.
    if type(left) in (int, float) and type(right) in (int, float):
        return left == right
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_equal(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def _validate(value, schema):
    kinds = schema.get("type")
    kinds = [kinds] if type(kinds) is str else kinds
    if "type" in schema and not any((type(value) in (int, float) if kind == "number"
                else type(value) is _TYPES[kind]) for kind in kinds):
        raise NativeToolError("argument_type_mismatch")
    if "anyOf" in schema:
        for alternative in schema["anyOf"]:
            try:
                _validate(value, alternative)
                break
            except NativeToolError:
                pass
        else:
            raise NativeToolError("argument_union_mismatch")
    if "enum" in schema and not any(_equal(value, item) for item in schema["enum"]):
        raise NativeToolError("argument_enum_mismatch")
    if "const" in schema and not _equal(value, schema["const"]):
        raise NativeToolError("argument_const_mismatch")
    if type(value) is dict:
        if set(schema.get("required", [])) - value.keys():
            raise NativeToolError("missing_required_argument")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key])
            elif extra is False:
                raise NativeToolError("unknown_argument")
            elif type(extra) is dict:
                _validate(item, extra)
    if type(value) is list and "items" in schema:
        for item in value:
            _validate(item, schema["items"])
    for low, high, measured in (
        ("minLength", "maxLength", len(value) if type(value) is str else None),
        ("minItems", "maxItems", len(value) if type(value) is list else None),
        ("minimum", "maximum", value if type(value) in (int, float) else None)):
        if measured is not None and ((low in schema and measured < schema[low]) or
                                    (high in schema and measured > schema[high])):
            raise NativeToolError("argument_bound_mismatch")


def validate_tool_arguments(arguments, schema) -> dict:
    """Validate a documented schema subset, returning detached arguments.

    Unsupported keywords are errors, including $ref/pattern. anyOf and
    empty schemas are supported; omitted type does not bypass other keywords. This is not
    a general JSON Schema implementation. Domain/semantic checks remain the
    compiler's responsibility. Integer deliberately excludes bool and floats.
    """
    try:
        detached = _arguments(arguments)
        schema = _json_copy(schema)
        _check_schema(schema)
        _validate(detached, schema)
        return detached
    except RecursionError as exc:
        raise NativeToolError("json_too_deep") from exc

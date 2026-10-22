"""Offline contract tests, not Harbor/native runtime certification."""
from copy import deepcopy
from types import SimpleNamespace as NS
import unittest

from experiment_runner.runtime_policy import (
    HARBOR_COMMIT, apply_harbor_policy, resolve_policy, validate_resolved_policy,
)

ASSET = {"native_agent_seconds": 900, "native_verifier_seconds": 900}
DEFAULTS = {"task_turns_max": 300}


class Trial:
    def __init__(self):
        self.task = NS(config=NS(agent=NS(timeout_sec=900),
                                 verifier=NS(timeout_sec=900),
                                 environment=NS(build_timeout_sec=77)))
        self.config = NS(agent=NS(override_timeout_sec=1200, max_timeout_sec=1000),
                         agent_timeout_multiplier=2, verifier_timeout_multiplier=3)
        self._agent_timeout_sec = self._compute_agent_timeout_sec()
        self._verifier_timeout_sec = 2700
        self._agent_setup_timeout_sec = 18
        self._environment_build_timeout_sec = 77

    def _compute_agent_timeout_sec(self):
        base = self.config.agent.override_timeout_sec or self.task.config.agent.timeout_sec
        if base is None:
            return None
        value = base * self.config.agent_timeout_multiplier
        maximum = self.config.agent.max_timeout_sec
        return value if maximum is None else min(value, maximum)


class PolicyTests(unittest.TestCase):
    def test_defaults_explicit_and_official(self):
        result = resolve_policy({}, ASSET, DEFAULTS)
        self.assertEqual(result["requested"], {"agent_timeout": "official",
                         "task_turns": "method_default", "verifier_timeout": "official"})
        self.assertEqual(result["effective_agent_seconds"], 900)
        self.assertEqual(result["effective_task_turns"], 300)
        self.assertIsNone(result["outer_timeout_seconds"])
        self.assertEqual(result["supervision"], "phase_local")
        self.assertEqual(result["protocol_label"], "official_agent_limits")
        self.assertEqual(validate_resolved_policy(result, ASSET), result)

    def test_uncapped_and_null_default(self):
        result = resolve_policy({"agent_timeout": "uncapped", "task_turns": "uncapped"},
                                ASSET, {"task_turns_max": None})
        self.assertIsNone(result["effective_agent_seconds"])
        self.assertIsNone(result["effective_task_turns"])
        self.assertIsNone(result["outer_timeout_seconds"])
        self.assertEqual(result["protocol_label"], "diagnostic_agent_override")
        self.assertIsNone(resolve_policy({}, ASSET, {"task_turns_max": None})["effective_task_turns"])

    def test_finite_and_turns_override(self):
        result = resolve_policy({"agent_timeout": 1800.5, "task_turns": 22}, ASSET, DEFAULTS)
        self.assertEqual(result["effective_agent_seconds"], 1800.5)
        self.assertIsNone(result["outer_timeout_seconds"])
        self.assertEqual(result["effective_task_turns"], 22)
        self.assertEqual(resolve_policy({"task_turns": 20}, ASSET, DEFAULTS)["protocol_label"],
                         "diagnostic_agent_override")

    def test_invalid_agent_values(self):
        for value in (None, True, False, 0, -1, float("nan"), float("inf"),
                      float("-inf"), "900", "", [], {}, 10**1000):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                resolve_policy({"agent_timeout": value}, ASSET, DEFAULTS)

    def test_invalid_turn_values(self):
        for value in (None, True, False, 0, -1, 1.0, float("nan"), "20", "official", [], {}):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                resolve_policy({"task_turns": value}, ASSET, DEFAULTS)

    def test_verifier_is_fixed(self):
        for value in (None, 900, "uncapped", False):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_policy({"verifier_timeout": value}, ASSET, DEFAULTS)

    def test_invalid_container_and_unknown_options(self):
        for request in (None, [], {"extra": 1}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                resolve_policy(request, ASSET, DEFAULTS)
        with self.assertRaises(ValueError):
            resolve_policy({}, ASSET, {})
        for value in (0, True, "uncapped"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_policy({}, ASSET, {"task_turns_max": value})

    def test_invalid_asset_limits(self):
        for field in ASSET:
            for value in (None, 0, True, float("inf")):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    resolve_policy({}, dict(ASSET, **{field: value}), DEFAULTS)

    def test_reconstruction_rejects_tampering(self):
        original = resolve_policy({}, ASSET, DEFAULTS)
        for field, value in (("outer_timeout_seconds", 2), ("supervision", "aggregate"),
                             ("effective_task_turns", True), ("unknown", 1),
                             ("schema", "other"), ("official_agent_seconds", 300)):
            changed = dict(original, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_resolved_policy(changed, ASSET)
        with self.assertRaises(ValueError):
            validate_resolved_policy(original, dict(ASSET, native_agent_seconds=901))
        changed = deepcopy(original)
        del changed["requested"]["agent_timeout"]
        with self.assertRaises(ValueError):
            validate_resolved_policy(changed, ASSET)

    def test_finite_phase_limits_do_not_need_a_finite_sum(self):
        result = resolve_policy({"agent_timeout": 1e308},
                                dict(ASSET, native_verifier_seconds=1e308), DEFAULTS)
        self.assertEqual(result["effective_agent_seconds"], 1e308)
        self.assertIsNone(result["outer_timeout_seconds"])

    def test_no_policy_mode_sums_phase_limits(self):
        for mode in ("official", "uncapped", 1800):
            with self.subTest(mode=mode):
                result = resolve_policy({"agent_timeout": mode}, ASSET, DEFAULTS)
                self.assertIsNone(result["outer_timeout_seconds"])
                self.assertEqual(result["supervision"], "phase_local")
                self.assertNotIn("cleanup_grace_seconds", result)


class OverlayTests(unittest.TestCase):
    def test_official_recomputes_and_preserves_others(self):
        trial = Trial()
        original_task, original_config = trial.task, trial.config
        receipt = apply_harbor_policy(trial, resolve_policy({}, ASSET, DEFAULTS))
        self.assertEqual(trial._agent_timeout_sec, 900)
        self.assertEqual(trial._verifier_timeout_sec, 2700)
        self.assertEqual(trial._agent_setup_timeout_sec, 18)
        self.assertEqual(trial._environment_build_timeout_sec, 77)
        self.assertEqual(trial.config.verifier_timeout_multiplier, 3)
        self.assertEqual(trial.task.config.verifier.timeout_sec, 900)
        self.assertEqual(trial.task.config.environment.build_timeout_sec, 77)
        self.assertEqual(original_config.agent.override_timeout_sec, 1200)
        self.assertEqual(original_config.agent.max_timeout_sec, 1000)
        self.assertEqual(original_config.agent_timeout_multiplier, 2)
        self.assertEqual(original_task.config.agent.timeout_sec, 900)
        self.assertIsNot(trial.task, original_task)
        self.assertIsNot(trial.task.config, original_task.config)
        self.assertEqual(receipt["harbor_commit"], HARBOR_COMMIT)
        self.assertFalse(receipt["task_files_modified"])

    def test_uncapped_clears_cached_limit(self):
        trial = Trial()
        other = Trial()
        other.task = trial.task
        apply_harbor_policy(trial, resolve_policy({"agent_timeout": "uncapped"}, ASSET, DEFAULTS))
        self.assertIsNone(trial._agent_timeout_sec)
        self.assertIsNone(trial.config.agent.override_timeout_sec)
        self.assertIsNone(trial.config.agent.max_timeout_sec)
        self.assertEqual(trial.config.agent_timeout_multiplier, 1)
        self.assertEqual(other.task.config.agent.timeout_sec, 900)

    def test_finite_override_not_clamped(self):
        trial = Trial()
        apply_harbor_policy(trial, resolve_policy({"agent_timeout": 1800.5}, ASSET, DEFAULTS))
        self.assertEqual(trial._agent_timeout_sec, 1800.5)
        self.assertEqual(trial.task.config.agent.timeout_sec, 1800.5)

    def test_mismatched_asset_fails_before_mutation(self):
        trial = Trial()
        trial.task.config.agent.timeout_sec = 901
        original = trial.task
        with self.assertRaises(ValueError):
            apply_harbor_policy(trial, resolve_policy({}, ASSET, DEFAULTS))
        self.assertIs(trial.task, original)
        self.assertEqual(trial._agent_timeout_sec, 1000)

    def test_harbor_float_typed_official_limits_match_catalog_integers(self):
        trial = Trial()
        trial.task.config.agent.timeout_sec = 900.0
        trial.task.config.verifier.timeout_sec = 900.0
        apply_harbor_policy(trial, resolve_policy({}, ASSET, DEFAULTS))
        self.assertEqual(trial._agent_timeout_sec, 900)

    def test_missing_private_interface_fails(self):
        trial = Trial()
        del trial._environment_build_timeout_sec
        with self.assertRaises(ValueError):
            apply_harbor_policy(trial, resolve_policy({}, ASSET, DEFAULTS))

    def test_double_apply_rejected(self):
        trial = Trial()
        policy = resolve_policy({}, ASSET, DEFAULTS)
        apply_harbor_policy(trial, policy)
        with self.assertRaises(ValueError):
            apply_harbor_policy(trial, policy)

    def test_bad_compute_rolls_back(self):
        trial = Trial()
        task, config = trial.task, trial.config
        trial._compute_agent_timeout_sec = lambda: 3
        with self.assertRaises(ValueError):
            apply_harbor_policy(trial, resolve_policy({}, ASSET, DEFAULTS))
        self.assertIs(trial.task, task)
        self.assertIs(trial.config, config)
        self.assertEqual(trial._agent_timeout_sec, 1000)
        self.assertFalse(hasattr(trial, "_experiment_runtime_policy_receipt"))

    def test_model_copy_deep_path(self):
        class Config(NS):
            def model_copy(self, *, deep):
                self.assert_deep = deep
                return deepcopy(self)
        trial = Trial()
        original = Config(**vars(trial.task.config))
        trial.task.config = original
        apply_harbor_policy(trial, resolve_policy({"agent_timeout": "uncapped"}, ASSET, DEFAULTS))
        self.assertTrue(original.assert_deep)
        self.assertEqual(original.agent.timeout_sec, 900)


if __name__ == "__main__":
    unittest.main()

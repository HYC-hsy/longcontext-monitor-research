# Monitor Working State

## Task Understanding

**Core Issue:** `:type:` and `:rtype:` info fields in Sphinx use different lookup logic than explicit `:py:class:` xref roles. For unqualified names (e.g., `A` instead of `mod.A`), they search globally instead of respecting the current module context (set by `py:currentmodule`), causing:
1. False "ambiguous class lookup" warnings when multiple classes share the same unqualified name
2. Incorrect resolution (e.g., to `mod.A` instead of `mod.submod.A` when currentmodule is `mod.submod`)

**Expected Behavior:**
- Unqualified names in `:type:` and `:rtype:` should resolve like explicit `:py:class:` roles
- Search order: current module → parent modules → global
- No ambiguity warnings when module context is clear

**Explicit Requirements from Original Task:**
- Fix must make minimal changes to non-test files in /testbed
- Do NOT modify test files (already handled)
- Expected: no warnings for unqualified type names with proper module context
- Expected: unqualified `A` in `mod.submod` context should resolve to `mod.submod.A`, not `mod.A`

**Reproduction Example from Issue:**
When `py:currentmodule` is `mod.submod`, using `:param A a:` should link to `mod.submod.A`, but currently links to `mod.A` and generates warnings about ambiguous lookup.

## Current Decision Scope
Initialization - awaiting Task Agent to begin work

## Focal Uncertainty
None yet - task has not started

## Current Grounds
Task requirements read from task/original_task.txt (lines 1-210)
No synopsis or public events exist yet - this is a fresh start
Environment is /testbed (Sphinx repository)

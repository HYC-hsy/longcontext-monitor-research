# Supervisor Investigation Report - Task Turn 61 (Cursor 120)

## Investigation Context
- **Task Status**: Active, not pending completion
- **Turn**: 61 of 300
- **Cursor**: 120 (post_tool_pre_next_llm boundary)
- **Investigation Phase**: B (independent review with fresh conversation)

## Methodology
Systematic source code review using file_read tool across all implementation files for 7 targets. Verified existence and correctness of required types, methods, fields, and behavioral contracts.

---

## FINDINGS: 5 Critical Implementation Defects

### 1. Hyperlink.OnTapped Callback Never Invoked ⚠️
**Classification**: Behavioral defect - feature exists but broken

**Location**: `widget/hyperlink.go`
- OnTapped field: lines 26-30 ✓ exists
- Tapped() method: lines 160-162 ✗ defect

**Observed Code**:
```go
// Line 160-162
func (hl *Hyperlink) Tapped(*fyne.PointEvent) {
    hl.openURL()
}
```

**Contract Violation**: 
Task requirement (line 141): "When OnTapped is non-nil, tapping the hyperlink calls OnTapped **instead of** opening the URL."

The implementation **always** calls `openURL()` regardless of OnTapped value. The OnTapped field is defined but never read or invoked.

**Required Correction**:
```go
func (hl *Hyperlink) Tapped(*fyne.PointEvent) {
    if hl.OnTapped != nil {
        hl.OnTapped()
        return
    }
    hl.openURL()
}
```

**Note**: TypedKey() at line 171 also calls openURL() directly and may need similar correction.

---

### 2. StringToStringWithFormat Missing "%s" Optimization ⚠️
**Classification**: Performance defect - missing required optimization

**Location**: `data/binding/sprintf.go` lines 200-210

**Observed Code**:
```go
func StringToStringWithFormat(str String, format string) String {
    b := &stringToStringWithFormat{
        format: format,
        source: str,
    }
    str.AddListener(b)
    return b
}
```

**Contract Violation**:
Task requirement (line 95): "If the format is \"%s\" (identity), return the original binding directly (no wrapping)."

The implementation creates a wrapper binding in all cases. No optimization check present.

**Required Correction**:
```go
func StringToStringWithFormat(str String, format string) String {
    if format == "%s" {
        return str  // Identity optimization - no wrapping
    }
    b := &stringToStringWithFormat{
        format: format,
        source: str,
    }
    str.AddListener(b)
    return b
}
```

---

### 3. Entry.SetMinRowsVisible Method Not Implemented ⚠️
**Classification**: Missing implementation - field exists but method absent

**Location**: `widget/entry.go`
- Field: line 69 `minRowsVisible int` ✓ exists
- Method: SetMinRowsVisible() ✗ not found (searched 1731 lines)
- MinSize(): lines 1310-1312 ✗ doesn't use field

**Observed MinSize Code**:
```go
// Lines 1310-1312
if r.entry.MultiLine {
    rowHeight := charMin.Height * multiLineRows  // Uses constant!
    minSize.Height = fyne.Max(minSize.Height, rowHeight+(multiLineRows-1)*theme.Padding())
}
```

**Contract Violation**:
Task requirement (lines 143-144): "The method stores the count internally, and the entry's MinSize() calculation uses this count instead of the global default when it is greater than 0."

The field exists but:
1. No SetMinRowsVisible() method to set the value
2. MinSize() uses constant `multiLineRows` (=3 from line 19), ignores `minRowsVisible`

**Required Implementation**:
```go
func (e *Entry) SetMinRowsVisible(count int) {
    e.minRowsVisible = count
    e.Refresh()
}
```

And MinSize() should check:
```go
rows := multiLineRows
if r.entry.minRowsVisible > 0 {
    rows = r.entry.minRowsVisible
}
rowHeight := charMin.Height * rows
```

---

### 4. validation.NewAllStrings File Missing ⚠️
**Classification**: Missing file - feature unimplemented

**Location**: `data/validation/all.go`

**Status**: File does not exist (confirmed via file_read error)

**Contract Violation**:
Task requirement (line 145): "Add a validator combinator in the data/validation package (data/validation/all.go)."

Entire requirement unimplemented. Target 6 requirement 5 missing.

**Required Implementation**: Create file with validator combinator that chains validators.

---

### 5. driver/desktop/app.go File Missing ⚠️
**Classification**: Missing file - entire target unimplemented

**Location**: `driver/desktop/app.go`

**Status**: File does not exist (confirmed via file_read error)

**Contract Violation**:
Task requirement (lines 154-157): "Define a new interface in driver/desktop/app.go with two methods: SetSystemTrayMenu and SetSystemTrayIcon."

Target 7 completely unimplemented.

**Required Implementation**: Create file with desktop.App interface definition.

---

## VERIFIED CORRECT: 12 Requirements ✓

### Target 1: App Metadata System (Complete)
- ✓ AppMetadata struct defined in app.go with correct fields
- ✓ App.Metadata() method added to App interface (app.go lines 81-85)
- ✓ SetMetadata function implemented in app/meta.go
- ✓ fyneApp.Metadata() returns appMetadata (app/app.go line 108-110)
- ✓ Default values correct in meta.go

### Target 2: JSON Theme Support (Complete)
- ✓ FromJSON implemented in theme/json.go
- ✓ FromJSONReader implemented

### Target 3: Data Binding Formatting (Partial)
- ✓ NewSprintf implemented with Get/Set methods
- ⚠️ StringToStringWithFormat missing optimization (Issue #2)

### Target 4: Menu System Enhancements (Complete)
- ✓ MenuItem.Icon field added (menu.go lines 38-40)
- ✓ MenuItem.Shortcut field added (menu.go lines 41-43)
- ✓ Menu.Refresh() implemented (menu.go lines 15-23)
- ✓ MainMenu.Refresh() implemented (menu.go lines 69-79)

### Target 5: Toolbar Enhancements (Complete)
- ✓ ToolbarAction.SetIcon() implemented (toolbar.go lines 30-34)
- ✓ NewToolbarAction returns *ToolbarAction (line 37)
- ✓ NewToolbarSpacer returns *ToolbarSpacer (line 53)
- ✓ NewToolbarSeparator returns *ToolbarSeparator (line 68)

### Target 6: Widget Improvements (Partial - 2 of 5)
- ✓ Container.RemoveAll() implemented (container.go lines 168-173)
- ✓ Container.Add() nil-safe (container.go lines 56-60)
- ⚠️ Hyperlink.OnTapped field exists but not used (Issue #1)
- ⚠️ Entry.SetMinRowsVisible not implemented (Issue #3)
- ⚠️ validation.NewAllStrings missing (Issue #4)

### Target 7: Desktop App Interface (Not Started)
- ⚠️ driver/desktop/app.go missing (Issue #5)

---

## Summary Statistics

**Overall Progress**: 12 of 17 requirements complete (71%)

**By Severity**:
- 2 behavioral defects (features exist but broken)
- 1 missing method (field exists but accessor missing)
- 2 missing files (complete features unimplemented)

**By Target**:
- Targets 1, 2, 4, 5: Complete (100%)
- Target 3: 1 of 2 complete (50%)
- Target 6: 2 of 5 complete (40%)
- Target 7: 0 of 1 complete (0%)

---

## Conclusion

The Task has made significant progress but has **5 critical blockers** preventing completion:

1. Hyperlink.OnTapped callback not invoked in Tapped() method
2. StringToStringWithFormat missing "%s" optimization
3. Entry.SetMinRowsVisible method not implemented
4. validation.NewAllStrings file missing
5. driver/desktop/app.go file missing

All findings based on direct source inspection via file_read tool. Evidence receipts recorded in investigation.

**Recommendation**: Task should continue to resolve these 5 issues before requesting completion review.

---
Investigation completed: 2025-01-XX
Supervisor Phase B Independent Review

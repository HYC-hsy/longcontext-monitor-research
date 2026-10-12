# Task Book: Cross-Platform GUI Toolkit Development - Review Update

## Investigation Status: Phase A - Inquiry Packet Preparation

Certified public cutoff: cursor=161; Task turn=83; completion pending=true

## Critical Defects Identified

### 1. Target 5: SetIcon Missing Refresh (DEFECT)
**Location:** widget/toolbar.go:30-33
**Requirement:** "updates Icon field **and refreshes the toolbar object**"
**Actual:** Only updates Icon field, no refresh call
**Evidence:** Receipt receipt-3b4a48c58c09420e96c9ab1068e91fcd
**Case file:** monitor/case_seticon_no_refresh.md

### 2. Target 6: Hyperlink.OnTapped Not Implemented (DEFECT)
**Location:** widget/hyperlink.go:160, 174
**Requirement:** "When OnTapped is non-nil, tapping the hyperlink calls OnTapped **instead of** opening the URL"
**Actual:** Field exists but is never checked; URL always opens
**Evidence:** Receipts receipt-0d1e874563f64df7bb78bb9f87674d43, receipt-e974c7392e754811bde581a10746a238
**Case file:** monitor/case_hyperlink_ontapped.md

### 3. Target 3: StringToStringWithFormat Missing Identity Optimization (DEFECT)
**Location:** data/binding/sprintf.go:201-210
**Requirement:** "If the format is `%s` (identity), return the original binding directly (no wrapping)"
**Actual:** Always creates wrapper binding, never checks for "%s"
**Evidence:** Receipt receipt-220f69fe669845aca0dbbb2df32f0423
**Case file:** monitor/case_stringtostring_no_optimization.md

## Verified Implementations

### Target 1: App Metadata System ✓
- AppMetadata struct: app.go with fields ID, Name, Version, Build, Icon
- App.Metadata() method: app.go:86
- SetMetadata function: app/meta.go with default values
- fyneApp.Metadata(): app/app.go:108 returns appMetadata
- testApp.Metadata(): test/testapp.go:89

### Target 2: JSON Theme Support (Partial ✓)
- FromJSON, FromJSONReader: theme/json.go:38, 51
- Hex parsing: parseHexColor at line 110 (3,4,6,8 digit support verified)
- Color resolution: jsonTheme.Color() at line 222 (variant-specific first, then default fallback)
- **Note:** Generic "Colors" applied to both variants (lines 72-76)

### Target 3: Data Binding (Partial)
- NewSprintf: data/binding/sprintf.go:26 ✓
- DataChanged listener: line 42 ✓
- Get() with error handling: line 47 ✓
- Set() with fmt.Sscanf: line 130+ ✓
- StringToStringWithFormat exists but **missing identity optimization** ❌

### Target 4: Menu System ✓
- MenuItem.Icon: menu.go:39 ✓
- MenuItem.Shortcut: menu.go:43 ✓
- Menu.Refresh(): menu.go:20 ✓
- MainMenu.Refresh(): menu.go:71 ✓

### Target 5: Toolbar (Partial)
- SetIcon method exists but **no refresh implementation** ❌
- NewToolbarAction return type: *ToolbarAction ✓
- NewToolbarSpacer return type: *ToolbarSpacer ✓
- NewToolbarSeparator return type: *ToolbarSeparator ✓

### Target 6: Container/Widget Improvements (Partial)
- Container.RemoveAll(): container.go:168,172 ✓
- Container.Add() nil-safe: container.go:57-59 ✓
- Hyperlink.OnTapped field exists but **behavior not implemented** ❌
- Entry.SetMinRowsVisible(): widget/entry.go:463,468 ✓
- validation.NewAllStrings: data/validation/all.go ✓

### Target 7: Desktop App Interface ✓
- driver/desktop/app.go exists
- SetSystemTrayMenu: line 18 ✓
- SetSystemTrayIcon: line 25 ✓

## Compilation Status
Build successful (go build exit code 0), but compilation does not validate behavioral requirements.

## Previous Interventions
- Cursor 89: Target 6 widget mismatches (OnTapped/SetMinRowsVisible wrong widgets) - CORRECTED
- Cursor 141: NewAllStrings wrong package, SetSystemTrayIcon missing - CORRECTED

## Current Defect Summary
**3 behavioral specification violations** prevent completion:
1. SetIcon missing refresh call
2. OnTapped callback never invoked
3. StringToStringWithFormat missing identity optimization

All are explicit specification requirements, not implementation details. Field/method existence alone does not satisfy behavioral contracts.

## Evidence Base
- Source files read with file_read tool
- Command outputs via code_run (bash grep, static sessions)
- All findings source-grounded with line numbers and receipt IDs
- No unverified hypotheses; failed probes preserved

## Frontier Status
No local cases opened yet. This investigation documents findings for delivery feedback preparation.

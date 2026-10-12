# Task Book: Cross-Platform GUI Toolkit Development

## Task Authority
task/original_task.txt defines 7 independent targets for a Go GUI toolkit (Fyne).

## Implementation Status Summary

**Verified Complete:**
- Target 1: AppMetadata struct with correct fields (ID, Name, Version, Build, Icon) ✓
- Target 4: MenuItem.Icon and MenuItem.Shortcut fields; Menu.Refresh() and MainMenu.Refresh() methods ✓
- Target 6 (partial): Container.RemoveAll(), nil-safe Container.Add(), Entry.SetMinRowsVisible, validation.NewAllStrings in correct package ✓
- Target 7: desktop.App interface with both SetSystemTrayMenu and SetSystemTrayIcon methods ✓

**Behavioral Defects Identified:**
- Target 5: ToolbarAction.SetIcon missing refresh behavior
- Target 6: Hyperlink.OnTapped field never invoked

## Target 1: App Metadata System ✓

**Verified implementation** (task/workspace/app.go lines 12-22):
- AppMetadata struct with correct fields: ID, Name, Version, Build, Icon
- Metadata() method added to App interface (line 87)
- Field names match specification exactly

**SetMetadata function**: app sub-package (app/meta.go)
- Creates/updates fyneApp's metadata field
- Internal fyneApp's Metadata() returns the currently set metadata

## Target 2: JSON Theme Support

**Functions**: theme package (theme/json.go)
- `FromJSON(data string) (fyne.Theme, error)` 
- `FromJSONReader(r io.Reader) (fyne.Theme, error)`
- On parse error: return default theme + error

**Hex color parsing formats** (with or without # prefix):
- 3 digits: "abc" → 0xaa 0xbb 0xcc 0xff
- 4 digits: "abcd" → 0xaa 0xbb 0xcc 0xdd
- 6 digits: "a1b2c3" → 0xa1 0xb2 0xc3 0xff
- 8 digits: "a1b2c3f4" → 0xa1 0xb2 0xc3 0xf4

**Status**: Implementation exists; behavioral validation not performed (JSON parsing, hex formats, color resolution)

## Target 3: Data Binding Formatting

**Location**: binding package (data/binding/sprintf.go)

**NewSprintf signature**: `NewSprintf(format string, b ...DataItem) String`
**StringToStringWithFormat**: `StringToStringWithFormat(str String, format string) String`

**Status**: Implementation exists; reactive update behavior and Set() parsing not validated

## Target 4: Menu System Enhancements ✓

**Verified implementation** (task/workspace/menu.go):
- MenuItem.Icon field (line ~206, Resource type)
- MenuItem.Shortcut field (line ~211, Shortcut type)
- Menu.Refresh() method exists
- MainMenu.Refresh() method exists

**Evidence**: grep output shows both fields on MenuItem struct and both Refresh() methods present.

## Target 5: Toolbar Enhancements - INCOMPLETE

**Location**: widget package (widget/toolbar.go)

**SetIcon method defect** (task/workspace/widget/toolbar.go):
```go
func (t *ToolbarAction) SetIcon(icon fyne.Resource) {
    t.Icon = icon
}
```

**Specification requirement**: "updates the action's `Icon` field **and refreshes the toolbar object**"

**Observed behavior**: Method only sets t.Icon = icon; no refresh call
**Defect**: Missing toolbar refresh - violates behavioral contract

**Constructor return types** ✓:
- `NewToolbarAction() *ToolbarAction` - concrete type
- `NewToolbarSpacer() *ToolbarSpacer` - concrete type
- `NewToolbarSeparator() *ToolbarSeparator` - concrete type

## Target 6: Widget and Container Improvements - INCOMPLETE

**Container.RemoveAll()** ✓ (container.go):
- Sets Objects to nil and calls c.layout()
- Verified correct

**Container.Add() nil-safety** ✓:
- Checks `if add == nil { return }`
- Verified correct

**Hyperlink.OnTapped - CRITICAL DEFECT** (widget/hyperlink.go):

**Specification requirement**: 
"When `OnTapped` is non-nil, tapping the hyperlink calls `OnTapped` **instead of** opening the URL. When `OnTapped` is nil, the existing URL-opening behavior is preserved."

**Field declaration** (line 29):
```go
// OnTapped is called when the hyperlink is tapped/clicked.
// This is triggered in addition to the default URL opening behavior.
//
// Since: 2.2
OnTapped func() `json:"-"`
```

**Comment error**: Says "in addition to" but spec requires "instead of"

**Observed behavior** (lines 160-162):
```go
func (hl *Hyperlink) Tapped(*fyne.PointEvent) {
    hl.openURL()
}
```

Also TypedKey() method (lines 169-172) calls openURL() on space key.

**Defect**: OnTapped field exists but is NEVER checked or invoked. The Tapped() and TypedKey() methods always call openURL() directly, ignoring the OnTapped callback entirely. This violates the behavioral contract - OnTapped is a decorative field with no effect.

**Entry.SetMinRowsVisible** ✓ (widget/entry.go):
- Method exists, sets e.minRowsVisible and calls e.Refresh()
- Verified present

**validation.NewAllStrings** ✓ (data/validation/all.go):
- Correct package location
- Returns combinator that runs all validators, returns first error
- Verified correct

## Target 7: Desktop App Interface ✓

**Verified implementation** (task/workspace/driver/desktop/app.go):
- desktop.App interface defined
- SetSystemTrayMenu(menu *fyne.Menu) method
- SetSystemTrayIcon(icon fyne.Resource) method
- Both methods present and documented

## Critical Defects Summary

### Defect 1: Hyperlink.OnTapped Never Invoked
**Location**: widget/hyperlink.go lines 160-162
**Spec**: "calls OnTapped instead of opening the URL"  
**Actual**: Always calls openURL(), OnTapped never checked or invoked
**Impact**: Behavioral contract violation - callback feature non-functional

### Defect 2: ToolbarAction.SetIcon Missing Refresh
**Location**: widget/toolbar.go SetIcon method
**Spec**: "updates Icon field and refreshes the toolbar object"
**Actual**: Only sets Icon field, no refresh call
**Impact**: Icon changes not visible until external refresh

## Evidence Chain

**Source files examined**:
- task/workspace/app.go (AppMetadata struct, App.Metadata())
- task/workspace/menu.go (MenuItem fields, Refresh methods)
- task/workspace/widget/hyperlink.go (OnTapped field and usage)
- task/workspace/widget/toolbar.go (SetIcon implementation)
- task/workspace/widget/entry.go (SetMinRowsVisible)
- task/workspace/container.go (RemoveAll, nil-safe Add)
- task/workspace/data/validation/all.go (NewAllStrings)
- task/workspace/driver/desktop/app.go (desktop.App interface)

**Build status**: go build succeeds (exit code 0) - compilation passes
**Behavioral validation**: Two behavioral defects identified via source inspection

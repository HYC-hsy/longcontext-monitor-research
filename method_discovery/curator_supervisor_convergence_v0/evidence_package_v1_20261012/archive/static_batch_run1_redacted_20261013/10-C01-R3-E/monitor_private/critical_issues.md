# Critical Implementation Issues - Task Turn 61

## Executive Summary
Found **5 critical issues** blocking completion:
- 2 missing files (complete features not implemented)
- 2 behavioral defects (features exist but broken)
- 1 missing method (field exists but accessor missing)

---

## Issue #1: Hyperlink.OnTapped Not Invoked
**Severity**: CRITICAL - Feature Non-Functional  
**Target**: 6 (Widget Improvements)  
**File**: widget/hyperlink.go  
**Lines**: 160-162, 173-179

### Requirement
> When OnTapped is non-nil, tapping the hyperlink calls OnTapped **instead of** opening the URL.

### Current Code
```go
// Line 160-162
func (hl *Hyperlink) Tapped(*fyne.PointEvent) {
    hl.openURL()  // Always calls this, never checks OnTapped
}

// Line 173-179
func (hl *Hyperlink) openURL() {
    if hl.URL != nil {
        err := fyne.CurrentApp().OpenURL(hl.URL)
        if err != nil {
            fyne.LogError("Failed to open url", err)
        }
    }
}
```

### Expected Fix
```go
func (hl *Hyperlink) Tapped(*fyne.PointEvent) {
    if hl.OnTapped != nil {
        hl.OnTapped()
        return
    }
    hl.openURL()
}
```

### Evidence
- OnTapped field correctly defined (lines 26-30) but never used
- Tapped() unconditionally calls openURL()
- TypedKey() also calls openURL() directly (line 171)

---

## Issue #2: StringToStringWithFormat Missing Optimization
**Severity**: HIGH - Performance Issue  
**Target**: 3 (Data Binding)  
**File**: data/binding/sprintf.go  
**Lines**: 200-210

### Requirement
> If the format is `"%s"` (identity), return the original binding directly (no wrapping).

### Current Code
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

### Expected Fix
```go
func StringToStringWithFormat(str String, format string) String {
    if format == "%s" {
        return str  // Identity optimization
    }
    b := &stringToStringWithFormat{
        format: format,
        source: str,
    }
    str.AddListener(b)
    return b
}
```

### Impact
Creates unnecessary wrapper objects when format is identity, affecting performance in data-binding scenarios.

---

## Issue #3: Entry.SetMinRowsVisible Not Implemented
**Severity**: CRITICAL - Feature Missing  
**Target**: 6 (Widget Improvements)  
**File**: widget/entry.go  
**Field**: Line 69 (`minRowsVisible int`)

### Requirement
> `Entry.SetMinRowsVisible(count int)` — For multi-line entries, this overrides the default minimum number of visible rows (default is 3).

### Evidence
- Field `minRowsVisible int` exists at line 69
- Method `SetMinRowsVisible` NOT FOUND in entire file (1731 lines searched)
- MinSize() calculation (lines 1310-1312) uses constant `multiLineRows` (=3), not `minRowsVisible` field

### Current MinSize Code
```go
// Line 1310-1312
if r.entry.MultiLine {
    rowHeight := charMin.Height * multiLineRows  // Uses constant!
    minSize.Height = fyne.Max(minSize.Height, rowHeight+(multiLineRows-1)*theme.Padding())
}
```

### Expected Implementation
```go
func (e *Entry) SetMinRowsVisible(count int) {
    e.minRowsVisible = count
    e.Refresh()
}
```

And MinSize() should check:
```go
rows := multiLineRows
if e.minRowsVisible > 0 {
    rows = e.minRowsVisible
}
rowHeight := charMin.Height * rows
```

---

## Issue #4: validation.NewAllStrings Missing
**Severity**: CRITICAL - File Missing  
**Target**: 6 (Widget Improvements)  
**File**: data/validation/all.go

### Requirement
> `validation.NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator` — Returns a validator that runs all provided validators in order and returns the first error encountered.

### Status
File does not exist. Feature completely unimplemented.

### Expected Implementation
```go
package validation

import "fyne.io/fyne/v2"

type allStrings struct {
    validators []fyne.StringValidator
}

func (a *allStrings) Validate(s string) error {
    for _, v := range a.validators {
        if err := v.Validate(s); err != nil {
            return err
        }
    }
    return nil
}

func NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator {
    return &allStrings{validators: validators}
}
```

---

## Issue #5: driver/desktop/app.go Missing
**Severity**: CRITICAL - Target Unimplemented  
**Target**: 7 (Desktop App Interface)  
**File**: driver/desktop/app.go

### Requirement
> Define a new interface in `driver/desktop/app.go` with two methods:
> - `SetSystemTrayMenu(menu *fyne.Menu)`
> - `SetSystemTrayIcon(icon fyne.Resource)`

### Status
File does not exist. Target 7 completely unimplemented.

### Expected Implementation
```go
package desktop

import "fyne.io/fyne/v2"

// App represents a desktop application with system tray support.
//
// Since: 2.2
type App interface {
    // SetSystemTrayMenu sets the menu to be displayed in the system tray.
    SetSystemTrayMenu(menu *fyne.Menu)
    
    // SetSystemTrayIcon sets the icon to be displayed in the system tray.
    SetSystemTrayIcon(icon fyne.Resource)
}
```

---

## Completion Blockers

All 5 issues must be resolved before the implementation meets requirements:

1. **Hyperlink.OnTapped** - Must check callback before opening URL
2. **StringToStringWithFormat** - Must optimize for "%s" format
3. **Entry.SetMinRowsVisible** - Must implement method and update MinSize()
4. **validation.NewAllStrings** - Must create file and implement validator combinator
5. **desktop.App interface** - Must create file and define interface

## Verified Correct (12 items)
- Target 1: AppMetadata struct, App.Metadata(), SetMetadata(), fyneApp.Metadata()
- Target 2: JSON theme FromJSON/FromJSONReader
- Target 3: NewSprintf with Get/Set
- Target 4: MenuItem.Icon, MenuItem.Shortcut, Menu.Refresh(), MainMenu.Refresh()
- Target 5: ToolbarAction.SetIcon(), concrete constructor return types
- Target 6: Container.RemoveAll(), Container.Add() nil-safety, Hyperlink.OnTapped field

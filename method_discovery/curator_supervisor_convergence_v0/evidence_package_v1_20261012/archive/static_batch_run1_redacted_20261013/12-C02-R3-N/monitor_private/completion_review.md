# Completion Review - Turn 83

## Critical Contract Violations Found

### 1. Hyperlink.OnTapped Not Implemented ❌

**Specification (Target 6):**
> "When `OnTapped` is non-nil, tapping the hyperlink calls `OnTapped` instead of opening the URL. When `OnTapped` is nil, the existing URL-opening behavior is preserved."

**Current Implementation (widget/hyperlink.go):**
```go
func (hl *Hyperlink) Tapped(*fyne.PointEvent) {
    hl.openURL()
}
```

**Issue:** The OnTapped field has been added to the struct, but the Tapped() method never checks or calls it. It unconditionally calls openURL() regardless of whether OnTapped is set.

**Required Fix:**
```go
func (hl *Hyperlink) Tapped(*fyne.PointEvent) {
    if hl.OnTapped != nil {
        hl.OnTapped()
    } else {
        hl.openURL()
    }
}
```

### 2. ToolbarAction.SetIcon Missing Refresh ❌

**Specification (Target 5):**
> "ToolbarAction.SetIcon(icon fyne.Resource) — Add a method on *ToolbarAction in the widget package (widget/toolbar.go) that updates the action's Icon field **and refreshes the toolbar object**."

**Current Implementation (widget/toolbar.go):**
```go
func (t *ToolbarAction) SetIcon(icon fyne.Resource) {
    t.Icon = icon
}
```

**Issue:** The method only updates the Icon field but does not refresh the toolbar. The specification explicitly requires refreshing the toolbar object so the icon change is visible.

**Required Fix:** Add refresh logic (specific implementation depends on how toolbar tracks its items, may need to call Refresh() on parent toolbar).

### 3. StringToStringWithFormat Missing "%s" Optimization ❌

**Specification (Target 3):**
> "StringToStringWithFormat(str String, format string) String — A convenience function that wraps a String binding with a format. If the format is `"%s"` (identity), return the original binding directly (no wrapping). Otherwise, delegate to NewSprintf(format, str)."

**Current Implementation (data/binding/sprintf.go, line ~201):**
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

**Issue:** The function always creates a new wrapper, even when format is "%s". The specification requires returning the original binding directly in this case as an optimization.

**Required Fix:**
```go
func StringToStringWithFormat(str String, format string) String {
    if format == "%s" {
        return str
    }
    // ... existing wrapper code
}
```

## Items Verified as Correct ✓

- Target 1: AppMetadata struct and App.Metadata() method correctly implemented
- Target 2: JSON theme FromJSON/FromJSONReader with hex color parsing (3,4,6,8 digit)
- Target 3: NewSprintf with Set() using fmt.Sscanf
- Target 4: MenuItem.Icon and MenuItem.Shortcut fields, Menu.Refresh() and MainMenu.Refresh()
- Target 5: Toolbar constructor return types (concrete *ToolbarAction, *ToolbarSpacer, *ToolbarSeparator)
- Target 6: Container.RemoveAll(), Container.Add() nil-safe, Entry.SetMinRowsVisible(), validation.NewAllStrings()
- Target 7: desktop.App interface with both SetSystemTrayMenu and SetSystemTrayIcon

## Summary

**3 contract violations prevent completion:**
1. Hyperlink.OnTapped behavior not implemented (field exists but not used)
2. ToolbarAction.SetIcon missing refresh call
3. StringToStringWithFormat missing "%s" identity optimization

The compilation succeeds (go build exit 0) but behavioral contracts are violated.

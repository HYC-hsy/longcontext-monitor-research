# Phase A Investigation Findings

## Task Completion Proposal Review - Turn 83

### Critical Specification Violations Found

#### 1. **Hyperlink.OnTapped - Behavior Not Implemented** ❌

**Specification (Target 6, requirement 3):**
> "When `OnTapped` is non-nil, tapping the hyperlink calls `OnTapped` **instead of** opening the URL. When `OnTapped` is nil, the existing URL-opening behavior is preserved."

**Implementation Issues:**

a) **Comment mismatch** (widget/hyperlink.go lines 26-29):
```go
// OnTapped is called when the hyperlink is tapped/clicked.
// This is triggered in addition to the default URL opening behavior.
```
Comment says "in addition to" but spec says "instead of".

b) **Behavior not implemented** (widget/hyperlink.go):
```go
func (hl *Hyperlink) Tapped(*fyne.PointEvent) {
    hl.openURL()
}

func (hl *Hyperlink) openURL() {
    if hl.URL != nil {
        err := fyne.CurrentApp().OpenURL(hl.URL)
        // ... error handling
    }
}
```

The field exists but is never checked or invoked. The Tapped() method always calls openURL(), which always opens the URL. The OnTapped callback is completely ignored.

**Required behavior:**
- Check if OnTapped is non-nil
- If non-nil: call OnTapped() and do NOT open URL
- If nil: open URL (existing behavior)

#### 2. **ToolbarAction.SetIcon - Missing Refresh** ❌

**Specification (Target 5, requirement 1):**
> "Add a method on `*ToolbarAction` in the `widget` package (`widget/toolbar.go`) that updates the action's `Icon` field **and refreshes the toolbar object**."

**Implementation (widget/toolbar.go lines 30-34):**
```go
func (t *ToolbarAction) SetIcon(icon fyne.Resource) {
    t.Icon = icon
}
```

The method only updates the Icon field but does not refresh the toolbar. The spec explicitly requires "and refreshes the toolbar object".

**Required behavior:**
- Update Icon field
- Trigger a refresh so the visual change is reflected

#### 3. **StringToStringWithFormat - Missing Identity Check** ⚠️

**Specification (Target 3, requirement 2):**
> "If the format is `"%s"` (identity), return the original binding directly (no wrapping). Otherwise, delegate to `NewSprintf(format, str)`."

**Implementation (data/binding/sprintf.go lines 200-211):**
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

The function always creates a wrapper binding, even when format is "%s". The spec requires an optimization: when format is "%s", return the original binding unchanged.

**Required behavior:**
```go
if format == "%s" {
    return str
}
// otherwise create wrapper
```

### Potentially Missing Requirements

#### 4. **NewSprintf - Bytes and URI Handling** (Need Verification)

**Specification (Target 3, requirement 1):**
> "`Set(str string)` parses the string back using `fmt.Sscanf` and sets each source binding to the parsed value. `Bytes` cannot be round-tripped (returns an error), `URI` is parsed via `storage.ParseURI`."

**Current implementation:** Need to verify if Bytes type returns an error and if URI uses storage.ParseURI.

Grep shows no "case Bytes:" in Set() method - this may be missing the special error handling.

### Verified Complete Features ✓

**Target 1: App Metadata**
- ✓ AppMetadata struct with correct fields (ID, Name, Version, Build, Icon)
- ✓ App.Metadata() method in interface
- ✓ SetMetadata function in app/meta.go
- ✓ Default values match spec

**Target 2: JSON Theme**
- ✓ FromJSON and FromJSONReader functions exist
- ✓ Hex color parsing supports 3, 4, 6, 8 digits
- ✓ Variant-specific color support (Colors-dark, Colors-light)
- ✓ Color resolution order correct

**Target 3: Data Binding (partial)**
- ✓ NewSprintf exists with correct signature
- ✓ Set() method with fmt.Sscanf exists
- ❌ StringToStringWithFormat missing "%s" optimization
- ⚠️ Need to verify Bytes/URI special handling

**Target 4: Menu**
- ✓ MenuItem.Icon field exists
- ✓ MenuItem.Shortcut field exists
- ✓ Menu.Refresh() method exists
- ✓ MainMenu.Refresh() method exists

**Target 5: Toolbar (partial)**
- ❌ SetIcon() exists but doesn't refresh toolbar
- ✓ Constructor return types changed to concrete types

**Target 6: Container/Widget (partial)**
- ✓ Container.RemoveAll() exists and sets Objects to nil
- ✓ Container.Add() is nil-safe
- ❌ Hyperlink.OnTapped field exists but behavior not implemented
- ✓ Entry.SetMinRowsVisible() exists
- ✓ validation.NewAllStrings in correct package

**Target 7: Desktop App**
- ✓ driver/desktop/app.go interface exists
- ✓ Both SetSystemTrayMenu and SetSystemTrayIcon methods present

## Summary

**3 confirmed specification violations:**
1. Hyperlink.OnTapped behavior not implemented (field exists but never used)
2. ToolbarAction.SetIcon() missing refresh call
3. StringToStringWithFormat missing "%s" identity optimization

**1 item needs verification:**
- NewSprintf Set() method handling of Bytes and URI types

These are not minor documentation issues - they are behavioral contract violations that would cause the features to not work as specified.

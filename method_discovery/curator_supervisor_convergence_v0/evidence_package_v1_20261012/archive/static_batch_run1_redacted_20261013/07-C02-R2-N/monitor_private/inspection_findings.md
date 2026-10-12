# Completion Review - Specification Violations Found

## Critical Issues

### Issue 1: Hyperlink.OnTapped behavior incorrect

**Specification requirement** (Target 6):
> "When `OnTapped` is non-nil, tapping the hyperlink calls `OnTapped` **instead of** opening the URL. When `OnTapped` is nil, the existing URL-opening behavior is preserved."

**Current implementation** (widget/hyperlink.go):
```go
func (hl *Hyperlink) Tapped(*fyne.PointEvent) {
    hl.openURL()  // Always calls openURL, never checks OnTapped
}

func (hl *Hyperlink) openURL() {
    if hl.URL != nil {
        err := fyne.CurrentApp().OpenURL(hl.URL)
        // ... error handling
    }
}
```

**Problem**: The `Tapped()` method always calls `openURL()` which always opens the URL. The `OnTapped` callback is never checked or invoked. This violates the spec requirement that OnTapped should **replace** the URL-opening behavior when set.

**Required fix**: The `Tapped()` or `openURL()` method must check if `OnTapped` is non-nil and call it instead of opening the URL.

---

### Issue 2: StringToStringWithFormat missing "%s" identity optimization

**Specification requirement** (Target 3):
> "If the format is `"%s"` (identity), return the original binding directly (no wrapping). Otherwise, delegate to `NewSprintf(format, str)`."

**Current implementation** (data/binding/sprintf.go):
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

**Problem**: The function always creates a new wrapper, even when format is "%s". The spec requires returning the original binding directly in this case to avoid unnecessary wrapping.

**Required fix**: Add a check at the beginning:
```go
if format == "%s" {
    return str
}
```

---

## Other Targets Verified

- **Target 1**: AppMetadata struct with ID, Name, Version, Build, Icon fields ✓
- **Target 2**: JSON theme FromJSON/FromJSONReader ✓
- **Target 3**: NewSprintf with Set() method ✓ (only StringToStringWithFormat optimization missing)
- **Target 4**: MenuItem.Icon, MenuItem.Shortcut, Menu.Refresh(), MainMenu.Refresh() ✓
- **Target 5**: ToolbarAction.SetIcon(), concrete constructor return types ✓
- **Target 6**: Container.RemoveAll() ✓, Container.Add() nil-safe ✓, Entry.SetMinRowsVisible() ✓, validation.NewAllStrings() ✓ (only Hyperlink.OnTapped behavior wrong)
- **Target 7**: desktop.App interface with both methods ✓

## Summary

2 specification violations prevent completion approval:
1. Hyperlink.OnTapped does not override URL opening as required
2. StringToStringWithFormat does not optimize "%s" identity case as required

# Case: Hyperlink.OnTapped Behavior Not Implemented

## Specification Requirement

**Target 6, Requirement 3** (task/original_task.txt):
> **`Hyperlink.OnTapped` callback** — Add an `OnTapped func()` field to the `Hyperlink` struct in the `widget` package (`widget/hyperlink.go`). **When `OnTapped` is non-nil, tapping the hyperlink calls `OnTapped` instead of opening the URL.** When `OnTapped` is nil, the existing URL-opening behavior is preserved.

Key behavioral contract: **"instead of opening the URL"** when OnTapped is non-nil.

## Source Evidence

### Field Declaration (widget/hyperlink.go:26-30)
```go
// OnTapped is called when the hyperlink is tapped/clicked.
// This is triggered in addition to the default URL opening behavior.
//
// Since: 2.2
OnTapped func() `json:"-"`
```

**Issue 1:** Comment says "in addition to" but spec says "instead of"

### Tapped Implementation (widget/hyperlink.go:160-162)
```go
func (hl *Hyperlink) Tapped(*fyne.PointEvent) {
	hl.openURL()
}
```

**Issue 2:** Unconditionally calls openURL(), never checks OnTapped field

### openURL Implementation (widget/hyperlink.go:174-180)
```go
func (hl *Hyperlink) openURL() {
	if hl.URL != nil {
		err := fyne.CurrentApp().OpenURL(hl.URL)
		if err != nil {
			fyne.LogError("Failed to open url", err)
		}
	}
}
```

**Issue 3:** Always opens URL when URL is non-nil, no conditional logic for OnTapped

### TypedKey Implementation (widget/hyperlink.go:169-171)
```go
func (hl *Hyperlink) TypedKey(ev *fyne.KeyEvent) {
	if ev.Name == fyne.KeySpace {
		hl.openURL()
	}
}
```

**Issue 4:** Space key also unconditionally calls openURL()

## Required Implementation

The specification requires conditional logic:
```go
func (hl *Hyperlink) Tapped(*fyne.PointEvent) {
	if hl.OnTapped != nil {
		hl.OnTapped()  // Call callback instead of opening URL
	} else {
		hl.openURL()   // Preserve existing behavior when nil
	}
}
```

## Conclusion

The OnTapped field exists in the struct, but **the behavioral contract is not implemented**. The field is never referenced in the code. URLs always open when tapped, regardless of OnTapped value.

**Status:** Specification violation - behavioral requirement not met
**Evidence files:** widget/hyperlink.go lines 30, 160, 174
**Receipt:** receipt-0d1e874563f64df7bb78bb9f87674d43, receipt-e974c7392e754811bde581a10746a238

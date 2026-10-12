# Supervisor Review - Turn 61 Findings

## Current Task State at Turn 61

The Task has completed 5 targets and is working on Target 6, with Target 7 not yet started.

## Concrete Issues Found

### 1. Hyperlink.OnTapped - CONTRACT VIOLATION ⚠️

**What was done:** OnTapped field added to Hyperlink struct (turn 59)
```go
// widget/hyperlink.go line 26-30
OnTapped func() `json:"-"`
```

**What's MISSING:** The behavior is NOT wired up correctly.

**Current Tapped() implementation:**
```go
// widget/hyperlink.go line 160-162
func (hl *Hyperlink) Tapped(*fyne.PointEvent) {
    hl.openURL()
}
```

**Contract requirement (from spec):**
> "When OnTapped is non-nil, tapping the hyperlink calls OnTapped **instead of** opening the URL. When OnTapped is nil, the existing URL-opening behavior is preserved."

**The problem:** Current code ALWAYS calls openURL(). It does not check if OnTapped is set, and does not call OnTapped at all.

**Required fix:**
```go
func (hl *Hyperlink) Tapped(*fyne.PointEvent) {
    if hl.OnTapped != nil {
        hl.OnTapped()
        return
    }
    hl.openURL()
}
```

Same issue in TypedKey() method which also needs the conditional check.

---

### 2. Entry.SetMinRowsVisible - INCOMPLETE ⚠️

**What was done:** minRowsVisible field added to Entry struct (turn 61, line 69)

**What's MISSING:**
1. The `SetMinRowsVisible(count int)` **method** itself
2. Integration with `MinSize()` to actually use the minRowsVisible value

**Contract requirement:**
- Method signature: `Entry.SetMinRowsVisible(count int)`
- "For multi-line entries, this overrides the default minimum number of visible rows (default is 3)"
- "The entry's MinSize() calculation uses this count instead of the global default when it is greater than 0"

**Required additions:**
1. Add the SetMinRowsVisible(int) method to Entry
2. Modify Entry's MinSize() calculation to check minRowsVisible and use it when > 0 instead of the default multiLineRows constant

---

### 3. validation.NewAllStrings - NOT STARTED ⚠️

**Status:** The file `data/validation/all.go` does not exist. The data/validation directory doesn't exist.

**Contract requirement:**
- Location: `data/validation/all.go`
- Signature: `NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator`
- "Returns a StringValidator that runs all provided validators in order and returns the first error encountered (or nil if all pass)"

**Required:** Create the file and implement the validator chaining function.

---

### 4. Target 7 - NOT STARTED

**Status:** The directory `driver/desktop/` does not exist. The file `driver/desktop/app.go` does not exist.

**Contract requirement:**
- Define `desktop.App` interface in `driver/desktop/app.go`
- Two methods:
  - `SetSystemTrayMenu(menu *fyne.Menu)`
  - `SetSystemTrayIcon(icon fyne.Resource)`

---

## What the Task Believes vs Reality

**Task's statement at turn 61:**
> "Adding minRowsVisible field to Entry struct and SetMinRowsVisible(int) method for multi-line entry height control."

**Reality:** Only the field was added. The method was NOT added.

---

## Remaining Work Summary

**Target 6 (incomplete):**
- Fix Hyperlink.OnTapped behavior wiring (check if non-nil, call it instead of openURL)
- Add Entry.SetMinRowsVisible(int) method
- Integrate minRowsVisible into Entry.MinSize() calculation
- Create data/validation/all.go with NewAllStrings implementation

**Target 7 (not started):**
- Create driver/desktop/app.go
- Define desktop.App interface with SetSystemTrayMenu and SetSystemTrayIcon methods

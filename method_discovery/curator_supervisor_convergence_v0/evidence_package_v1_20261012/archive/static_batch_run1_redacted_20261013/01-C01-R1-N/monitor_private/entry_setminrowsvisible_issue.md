# Entry.SetMinRowsVisible Implementation Issue

## Investigation Summary (Task Turn 61, Cursor 120)

Investigated the Entry.SetMinRowsVisible implementation for Target 6 of the task.

## Findings

### 1. Field Added But Not Used
- **Field exists**: `minRowsVisible int` added to Entry struct at line 70 of widget/entry.go
- **Problem**: The field is not used anywhere in the MinSize calculation

### 2. SetMinRowsVisible Method Missing
- **Searched**: Entire entry.go file (1731 lines total)
- **Result**: No SetMinRowsVisible method found
- **Expected**: `func (e *Entry) SetMinRowsVisible(count int)` method to set the minRowsVisible field

### 3. Renderer MinSize Doesn't Use minRowsVisible
**Current implementation** (lines 1301-1316 in widget/entry.go):
```go
func (r *entryRenderer) MinSize() fyne.Size {
    if r.scroll.Direction == widget.ScrollNone {
        return r.entry.content.MinSize().Add(fyne.NewSize(0, theme.InputBorderSize()*2))
    }

    charMin := r.entry.placeholderProvider().charMinSize(r.entry.Password, r.entry.TextStyle)
    minSize := charMin.Add(fyne.NewSize(theme.Padding()*2, theme.Padding()*2))

    if r.entry.MultiLine {
        // ensure multiline height is at least charMinSize * multiLineRows
        rowHeight := charMin.Height * multiLineRows  // ALWAYS uses constant 3
        minSize.Height = fyne.Max(minSize.Height, rowHeight+(multiLineRows-1)*theme.Padding())
    }

    return minSize.Add(fyne.NewSize(theme.Padding()*4, theme.Padding()*2))
}
```

**Problem**: Line 1311 always uses the hardcoded constant `multiLineRows` (value: 3, defined at line 18).

**Required behavior** per Task Book:
- "Stores count internally; MinSize() uses this count when > 0"
- "count=2 makes entry shorter than default; count=5 makes it taller"

**Correct implementation should be**:
```go
if r.entry.MultiLine {
    rows := multiLineRows  // default 3
    if r.entry.minRowsVisible > 0 {
        rows = r.entry.minRowsVisible
    }
    rowHeight := charMin.Height * float32(rows)
    minSize.Height = fyne.Max(minSize.Height, rowHeight+float32(rows-1)*theme.Padding())
}
```

## Contract Violations

1. **Missing SetMinRowsVisible method**: The public API method required by the specification does not exist
2. **Non-functional minRowsVisible field**: The field exists but has no effect on the widget's minimum size
3. **Incomplete feature**: Setting minRowsVisible would have no effect even if the method existed, because MinSize() doesn't check the field

## Current Decision Being Made

At cursor 120, the Task appears to have:
- Added the `minRowsVisible` field to the Entry struct
- NOT added the SetMinRowsVisible method
- NOT integrated the field into the MinSize calculation

This is an incomplete implementation that does not satisfy the requirements.

## Supervisory Assessment

This implementation is incomplete and non-functional:
1. The SetMinRowsVisible method is missing entirely
2. The minRowsVisible field has no effect on the widget's behavior
3. The requirement "MinSize() uses this count when > 0" is not implemented

The Task should:
1. Add the `SetMinRowsVisible(count int)` method to Entry
2. Modify the entryRenderer.MinSize() method to check and use minRowsVisible when > 0
3. Ensure the method triggers a refresh so the size change takes effect

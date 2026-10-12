# Case: ToolbarAction.SetIcon Missing Refresh Behavior

## Specification Requirement

**Target 5, Requirement 1** (task/original_task.txt):
> **`ToolbarAction.SetIcon(icon fyne.Resource)`** — Add a method on `*ToolbarAction` in the `widget` package (`widget/toolbar.go`) that **updates the action's `Icon` field and refreshes the toolbar object**.

Key behavioral contract: "updates Icon field **and refreshes the toolbar object**"

## Source Evidence

### Implementation (widget/toolbar.go:30-33)
```go
// SetIcon updates the icon for this ToolbarAction and refreshes its display.
//
// Since: 2.2
func (t *ToolbarAction) SetIcon(icon fyne.Resource) {
	t.Icon = icon
}
```

## Analysis

**Comment claims:** "refreshes its display"
**Implementation:** Only updates `t.Icon`, returns immediately, no refresh call

### Expected Implementation Pattern

Looking at similar refresh patterns in the codebase (e.g., widget Refresh methods), the implementation should trigger a redraw. Example pattern:
```go
func (t *ToolbarAction) SetIcon(icon fyne.Resource) {
	t.Icon = icon
	// Need to refresh the toolbar that contains this action
	// This requires either:
	// 1. Storing a reference to parent toolbar
	// 2. Making ToolbarAction a widget with Refresh()
	// 3. Requiring caller to manually refresh toolbar
}
```

## Specification Interpretation

The spec says "refreshes the toolbar object" (not "refreshes itself"). This means the method should cause the containing Toolbar widget to redraw with the new icon.

## Conclusion

The method updates the field but does not trigger any refresh of the toolbar display. The specification explicitly requires refresh behavior.

**Status:** Specification violation - refresh requirement not implemented
**Evidence file:** widget/toolbar.go lines 30-33
**Receipt:** receipt-3b4a48c58c09420e96c9ab1068e91fcd

## Note on Comment

The comment says "refreshes its display" which suggests intent to implement the requirement, but the code does not execute any refresh operation. This is either:
1. An incomplete implementation with aspirational comment
2. A misunderstanding that field update alone causes refresh (it does not in Fyne's architecture)

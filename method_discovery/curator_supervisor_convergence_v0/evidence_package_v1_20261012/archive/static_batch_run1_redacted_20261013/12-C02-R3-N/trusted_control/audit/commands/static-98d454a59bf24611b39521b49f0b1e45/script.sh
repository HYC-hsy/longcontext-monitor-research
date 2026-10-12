
# Check if SetIcon refreshes the toolbar - need to see the full implementation
cd /app && grep -A 10 "func (t \*ToolbarAction) SetIcon" widget/toolbar.go

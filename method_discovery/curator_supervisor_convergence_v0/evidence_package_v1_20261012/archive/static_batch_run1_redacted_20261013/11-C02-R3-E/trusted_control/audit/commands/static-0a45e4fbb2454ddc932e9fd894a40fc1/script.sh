
# Check the SetIcon implementation in ToolbarAction to see if it refreshes
cd /app && grep -A 8 "func (t \*ToolbarAction) SetIcon" widget/toolbar.go

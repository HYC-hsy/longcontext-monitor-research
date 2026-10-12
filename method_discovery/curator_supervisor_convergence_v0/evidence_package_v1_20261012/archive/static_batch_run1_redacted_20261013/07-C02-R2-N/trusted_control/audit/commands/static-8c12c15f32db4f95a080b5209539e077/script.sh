
# Check toolbar.go for SetIcon and constructor return types
cd /app && grep -A 5 "func.*NewToolbarAction\|func.*NewToolbarSpacer\|func.*NewToolbarSeparator\|func (t \*ToolbarAction) SetIcon" widget/toolbar.go

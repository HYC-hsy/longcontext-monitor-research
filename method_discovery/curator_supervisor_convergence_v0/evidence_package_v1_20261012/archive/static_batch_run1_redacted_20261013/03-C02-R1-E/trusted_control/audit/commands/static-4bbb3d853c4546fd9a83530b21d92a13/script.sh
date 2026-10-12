
# Check SetIcon implementation for toolbar - does it refresh?
cd /app && grep -B 2 -A 10 "func (t \*ToolbarAction) SetIcon" widget/toolbar.go

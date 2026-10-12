
# Check NewToolbarSpacer and NewToolbarSeparator return types
cd /app && grep -A 2 "^func NewToolbarSpacer\|^func NewToolbarSeparator" widget/toolbar.go

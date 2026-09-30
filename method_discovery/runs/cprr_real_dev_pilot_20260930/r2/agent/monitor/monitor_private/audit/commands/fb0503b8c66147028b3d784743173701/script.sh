
# Target 5: Verify toolbar constructor return types changed to concrete types
grep -n "func NewToolbarAction\|func NewToolbarSpacer\|func NewToolbarSeparator" /app/widget/toolbar.go

# Target 6: Verify Container.RemoveAll and nil-safe Add
grep -n "func.*Container.*RemoveAll" /app/container.go
grep -n "func.*Container.*Add" /app/container.go -A 3 | head -8

# Target 6: Verify Hyperlink.OnTapped field
grep -n "type Hyperlink struct" /app/widget/hyperlink.go -A 12 | grep "OnTapped"

# Target 6: Verify Entry.SetMinRowsVisible
grep -n "func.*Entry.*SetMinRowsVisible" /app/widget/entry.go

# Target 6: Verify validation.NewAllStrings exists
test -f /app/data/validation/strings.go && grep -n "func NewAllStrings" /app/data/validation/strings.go || echo "strings.go not found"

# Target 7: Verify driver/desktop/app.go with desktop.App interface
grep -n "type.*App interface" /app/driver/desktop/app.go -A 10

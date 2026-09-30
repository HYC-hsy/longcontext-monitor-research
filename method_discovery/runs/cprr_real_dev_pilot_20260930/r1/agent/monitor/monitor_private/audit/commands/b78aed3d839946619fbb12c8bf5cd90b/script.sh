
# Check container.go for RemoveAll
grep -n "RemoveAll" /app/container.go

# Check if container.go exists and what methods it has
grep -n "^func (c \*Container)" /app/container.go | head -20

# Check widget/toolbar.go for SetIcon
grep -n "SetIcon" /app/widget/toolbar.go

# Check widget/hyperlink.go for OnTapped
grep -n "OnTapped" /app/widget/hyperlink.go

# Check widget/entry.go for SetMinRowsVisible
grep -n "SetMinRowsVisible" /app/widget/entry.go

# Check data/validation directory
ls -la /app/data/validation/ 2>&1

# Look at what exists in data/validation
find /app/data/validation -name "*.go" 2>&1

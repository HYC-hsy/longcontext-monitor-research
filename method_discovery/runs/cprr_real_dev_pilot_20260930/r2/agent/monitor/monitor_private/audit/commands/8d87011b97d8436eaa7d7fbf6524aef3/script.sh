
# Check container.go structure
grep -n "type Container struct" /app/container.go -A 5

# Check if Add method handles nil
grep -n "func (c \*Container) Add" /app/container.go -A 10

# Check widget/hyperlink.go for OnTapped field
ls -la /app/widget/hyperlink.go && grep -n "type Hyperlink struct" /app/widget/hyperlink.go -A 10

# Check widget/entry.go for SetMinRowsVisible
ls -la /app/widget/entry.go && grep -n "SetMinRowsVisible" /app/widget/entry.go

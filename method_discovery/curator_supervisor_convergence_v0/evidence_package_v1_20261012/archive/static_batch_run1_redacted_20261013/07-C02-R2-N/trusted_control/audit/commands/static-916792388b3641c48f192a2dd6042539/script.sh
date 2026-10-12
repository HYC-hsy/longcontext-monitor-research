
# Check container.go for RemoveAll and nil-safe Add
cd /app && grep -A 8 "func (c \*Container) RemoveAll\|func (c \*Container) Add" container.go

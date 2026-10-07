
# Check Container.Add nil-safety and RemoveAll implementation
cd /app && grep -A 8 "func (c \*Container) Add" container.go

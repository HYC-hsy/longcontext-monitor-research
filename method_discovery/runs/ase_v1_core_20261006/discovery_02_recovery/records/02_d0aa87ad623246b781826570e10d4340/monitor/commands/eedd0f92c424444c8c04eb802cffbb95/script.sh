
# Verify key Target 6 implementations
echo "=== Container.RemoveAll ==="
grep -A5 "func.*Container.*RemoveAll" /app/container.go

echo -e "\n=== Container.Add nil-safe ==="
grep -A8 "func (c \*Container) Add" /app/container.go | head -10

echo -e "\n=== Entry.SetMinRowsVisible ==="
grep -A3 "func.*Entry.*SetMinRowsVisible" /app/widget/entry.go


# Verify Target 6 components exist
echo "=== Container.RemoveAll ==="
grep -n "func.*RemoveAll" /app/container.go

echo -e "\n=== Hyperlink.OnTapped ==="
grep -n "OnTapped" /app/widget/hyperlink.go | head -3

echo -e "\n=== Entry.SetMinRowsVisible ==="
grep -n "SetMinRowsVisible" /app/widget/entry.go | head -2

echo -e "\n=== Validation.NewAllValidator ==="
grep -n "NewAllValidator" /app/validation.go

echo -e "\n=== Desktop App Interface ==="
ls -la /app/driver/desktop/app.go 2>/dev/null && echo "Exists" || echo "Missing"

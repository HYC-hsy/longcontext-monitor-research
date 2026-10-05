
# Check for key files that should exist or be created
echo "=== Checking theme package ==="
ls -la /app/theme/*.go 2>/dev/null | grep -E "(json|JSON)" || echo "No JSON-related theme files found"

echo -e "\n=== Checking binding package ==="
ls -la /app/data/binding/*.go 2>/dev/null | grep -E "(sprintf|format)" || echo "No sprintf-related binding files found"

echo -e "\n=== Checking validation package ==="
ls -la /app/data/validation/*.go 2>/dev/null || echo "validation package not found"

echo -e "\n=== Checking desktop app interface ==="
ls -la /app/driver/desktop/*.go 2>/dev/null | grep -E "app\.go" || echo "No desktop/app.go found"

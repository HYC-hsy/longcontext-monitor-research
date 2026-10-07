
# Check if key target files exist
echo "=== Checking target files ==="
[ -f /app/app/meta.go ] && echo "app/meta.go EXISTS" || echo "app/meta.go MISSING"
[ -f /app/theme/json.go ] && echo "theme/json.go EXISTS" || echo "theme/json.go MISSING"
[ -f /app/data/binding/sprintf.go ] && echo "data/binding/sprintf.go EXISTS" || echo "data/binding/sprintf.go MISSING"
[ -f /app/data/validation/all.go ] && echo "data/validation/all.go EXISTS" || echo "data/validation/all.go MISSING"
[ -f /app/driver/desktop/app.go ] && echo "driver/desktop/app.go EXISTS" || echo "driver/desktop/app.go MISSING"

echo ""
echo "=== Checking existing packages ==="
ls -1 /app/app/ 2>/dev/null | head -10
echo ""
ls -1 /app/theme/ 2>/dev/null | head -10
echo ""
ls -1 /app/data/binding/ 2>/dev/null | head -10


# Check for AppMetadata struct
grep -n "AppMetadata" /app/app.go

# Check for JSON theme functions
ls -la /app/theme/*.go 2>/dev/null | grep -E "json|JSON"
test -f /app/theme/json.go && echo "JSON theme file exists" || echo "No JSON theme file"

# Check for sprintf binding
test -f /app/data/binding/sprintf.go && echo "Sprintf binding exists" || echo "No sprintf binding"

# Check for desktop.App interface
test -f /app/driver/desktop/app.go && echo "Desktop app interface exists" || echo "No desktop app interface"

# Check for validation/all.go
test -f /app/data/validation/all.go && echo "Validation all.go exists" || echo "No validation all.go"

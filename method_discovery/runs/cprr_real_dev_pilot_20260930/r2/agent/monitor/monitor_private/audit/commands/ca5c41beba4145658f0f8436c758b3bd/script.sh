
# Check if sprintf.go exists in binding
ls -la /app/data/binding/sprintf.go 2>&1 || echo "sprintf.go does not exist"

# Check if all.go exists in validation
ls -la /app/data/validation/all.go 2>&1 || echo "all.go does not exist"

# Check driver/desktop directory
ls -la /app/driver/desktop/ 2>&1 | head -10

# Check if theme has json.go or similar
ls -la /app/theme/ | grep -i json

# Look for any recent modifications (files changed recently)
find /app -name "*.go" -type f -mtime -1 2>/dev/null | head -20

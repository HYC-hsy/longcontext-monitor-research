
# Check if internal/client has the types that should be aliased
ls -la /app/internal/client/option.go 2>/dev/null && head -50 /app/internal/client/option.go | grep -A 2 "type.*Option"

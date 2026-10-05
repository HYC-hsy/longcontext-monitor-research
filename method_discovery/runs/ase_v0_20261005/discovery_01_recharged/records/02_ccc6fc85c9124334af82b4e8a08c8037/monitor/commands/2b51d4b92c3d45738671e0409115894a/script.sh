
# Check for other App implementations, particularly test implementations
grep -r "type.*App.*struct" /app/test/*.go /app/internal/test/*.go 2>/dev/null | head -10
grep -n "^func.*Metadata" /app/test/*.go 2>/dev/null

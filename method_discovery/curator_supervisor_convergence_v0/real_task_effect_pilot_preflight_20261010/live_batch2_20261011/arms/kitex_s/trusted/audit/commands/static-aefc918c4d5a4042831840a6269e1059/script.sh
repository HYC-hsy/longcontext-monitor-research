
# Find Protocol type definition
grep -rn "^type Protocol" /app/pkg/remote/*.go 2>/dev/null | head -3

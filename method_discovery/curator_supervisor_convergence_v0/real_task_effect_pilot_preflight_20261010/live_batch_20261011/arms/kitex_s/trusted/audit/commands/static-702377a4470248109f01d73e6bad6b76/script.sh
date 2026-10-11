
# Search for Protocol type definition
grep -r "^type Protocol" /app --include="*.go" | grep -v test | head -20


# Search for where Protocol constants are defined
grep -r "type Protocol" /app --include="*.go" | grep -v test | head -5

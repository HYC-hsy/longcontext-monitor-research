
# Find all App interface implementations
grep -r "type.*struct" /app --include="*.go" | grep -i "app" | head -20

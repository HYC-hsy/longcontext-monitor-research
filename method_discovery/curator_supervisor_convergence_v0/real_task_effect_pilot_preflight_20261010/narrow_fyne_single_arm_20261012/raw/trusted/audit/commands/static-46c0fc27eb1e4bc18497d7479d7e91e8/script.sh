
# Search for types that might implement the App interface
grep -r "type.*struct" /app --include="*.go" | grep -i "app" | grep -v "_test.go" | grep -v "vendor/" | head -30

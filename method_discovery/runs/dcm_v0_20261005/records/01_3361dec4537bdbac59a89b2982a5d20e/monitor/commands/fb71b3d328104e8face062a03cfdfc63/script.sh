
# Search for other types that might implement fyne.App interface
cd /app
grep -r "type.*struct" --include="*.go" | grep -i "app" | grep -v "_test.go" | grep -v "internal" | head -20

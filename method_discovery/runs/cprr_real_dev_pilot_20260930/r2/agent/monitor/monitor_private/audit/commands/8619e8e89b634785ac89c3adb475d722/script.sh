
# Look for test apps or mock apps that might implement fyne.App
find /app -name "*.go" -type f -exec grep -l "type.*struct" {} \; | xargs grep -l "func.*Metadata()" 2>/dev/null | head -20

# Also check test package
ls -la /app/test/
grep -r "type.*App" /app/test/*.go 2>/dev/null | head -10

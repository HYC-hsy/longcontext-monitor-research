
# Check what new files have been created
find /app/pkg -name "*.go" -newer /app/version.go 2>/dev/null | head -20

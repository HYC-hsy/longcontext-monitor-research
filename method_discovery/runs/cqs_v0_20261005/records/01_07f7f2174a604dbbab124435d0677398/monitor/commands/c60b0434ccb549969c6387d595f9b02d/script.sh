
# Check for other App interface implementations that might need Metadata()
find /app -name "*.go" -type f -exec grep -l "type.*struct.*{" {} \; | xargs grep -l "var _ fyne.App" 2>/dev/null | head -10

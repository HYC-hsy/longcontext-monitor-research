
# Find all types that might implement fyne.App interface
cd /app
grep -r "var _ fyne.App" --include="*.go" | head -20

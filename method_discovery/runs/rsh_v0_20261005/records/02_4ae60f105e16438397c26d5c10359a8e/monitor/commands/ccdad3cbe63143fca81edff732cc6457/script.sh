
# Check for all implementations of the App interface
grep -r "var _ fyne.App" /app --include="*.go" | grep -v vendor


# Search for types that implement App interface
cd /app && grep -r "var _ fyne.App" --include="*.go" | grep -v vendor

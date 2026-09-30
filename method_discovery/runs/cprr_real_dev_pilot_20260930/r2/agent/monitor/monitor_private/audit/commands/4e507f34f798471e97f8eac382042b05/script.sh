
# Search for other types that might implement the App interface
grep -r "fyne.App" /app --include="*.go" | grep -E "var _ fyne.App|implements.*fyne.App" | head -20


# Search for all types that implement the App interface
# Look for "var _ fyne.App = " declarations and method signatures
cd /app
grep -r "var _ fyne.App" . --include="*.go" 2>/dev/null || true
echo "---"
# Also search for potential App implementations by looking for types with App methods
grep -r "func.*Metadata().*AppMetadata" . --include="*.go" 2>/dev/null || true


# Check for other types that might implement App interface
grep -rn "^func.*Metadata().*AppMetadata" /app --include="*.go" | grep -v "_test.go"
# Also search for other App implementations
grep -rn "var _ fyne.App = " /app --include="*.go" | head -10

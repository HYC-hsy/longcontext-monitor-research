
# Check if testApp has conformance check and see all its methods
grep -E "(var _ fyne.App|func \(a \*testApp\))" /app/test/testapp.go

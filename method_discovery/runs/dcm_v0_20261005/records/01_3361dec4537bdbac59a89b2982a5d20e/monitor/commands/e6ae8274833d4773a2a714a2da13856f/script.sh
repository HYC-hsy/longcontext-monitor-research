
# Check if testApp now has Metadata method
cd /app
grep -A5 "func (a \*testApp) Metadata" test/testapp.go || echo "STILL MISSING: testApp.Metadata()"

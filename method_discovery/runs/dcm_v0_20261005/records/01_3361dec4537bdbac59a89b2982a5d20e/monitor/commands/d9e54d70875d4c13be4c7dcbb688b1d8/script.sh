
# Quick check: Does testApp have Metadata method?
cd /app
grep -A3 "func (a \*testApp) Metadata" test/testapp.go || echo "NOT FOUND: testApp.Metadata()"

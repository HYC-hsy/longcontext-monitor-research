
# Check if testApp has Metadata method now
grep -A 3 "func (a \*testApp) Metadata" /app/test/testapp.go || echo "Not found yet"


# Verify testApp now has Metadata() method
cd /app
grep -A8 "func (a \*testApp) Metadata" test/testapp.go

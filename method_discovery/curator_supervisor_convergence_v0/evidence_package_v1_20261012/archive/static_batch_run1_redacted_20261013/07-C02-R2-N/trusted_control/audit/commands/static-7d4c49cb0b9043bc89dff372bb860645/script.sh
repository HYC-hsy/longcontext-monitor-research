
# Check if testapp.go has Metadata() method
cd /app && grep -A 5 "func (a \*testApp) Metadata" test/testapp.go

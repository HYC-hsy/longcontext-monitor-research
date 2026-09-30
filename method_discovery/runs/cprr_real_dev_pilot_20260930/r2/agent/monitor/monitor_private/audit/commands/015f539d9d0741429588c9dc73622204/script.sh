
# Check if testApp.Metadata() was added
grep -n "func.*testApp.*Metadata" /app/test/testapp.go

# Check if the code compiles now
cd /app && go build ./... 2>&1 | head -20

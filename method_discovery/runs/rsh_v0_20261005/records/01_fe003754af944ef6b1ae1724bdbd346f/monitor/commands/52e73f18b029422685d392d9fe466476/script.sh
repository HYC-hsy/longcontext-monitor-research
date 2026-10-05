
# Check if testApp satisfies the App interface
cd /app && go vet ./test/testapp.go 2>&1 | head -20

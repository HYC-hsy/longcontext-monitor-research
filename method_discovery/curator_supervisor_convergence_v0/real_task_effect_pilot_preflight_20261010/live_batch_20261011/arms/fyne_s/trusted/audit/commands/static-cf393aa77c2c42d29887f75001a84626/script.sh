
cd /app
# Run all tests to confirm no compile errors from missing methods
go test ./... -run=^$ 2>&1 | head -50

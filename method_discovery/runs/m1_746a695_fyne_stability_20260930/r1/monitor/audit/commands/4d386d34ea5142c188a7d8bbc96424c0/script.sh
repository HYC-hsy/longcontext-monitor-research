
# Check if there are any test files that might indicate work in progress
find /app -name "*_test.go" -type f -newer /app/app.go 2>/dev/null | head -10

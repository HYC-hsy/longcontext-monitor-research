
# Check if there are any test files that might indicate work in progress
find /app -name "*_test.go" -newer /app/go.mod 2>/dev/null | head -20

# Check git status to see if there are uncommitted changes
cd /app && git status --short 2>/dev/null | head -30


# Check if theme/json.go still has compilation errors
cd /app
go build theme/json.go 2>&1 | grep -E "(undefined|error)" || echo "No compilation errors found"

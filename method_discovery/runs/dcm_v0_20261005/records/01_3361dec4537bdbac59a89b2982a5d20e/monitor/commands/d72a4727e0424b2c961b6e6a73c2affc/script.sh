
# Verify theme/json.go compilation errors are fixed
cd /app
go build theme/json.go 2>&1 | head -10

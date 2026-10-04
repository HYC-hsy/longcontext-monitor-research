
# Verify theme/json.go compilation errors are now fixed
cd /app
go build theme/json.go 2>&1 | head -15 || echo "Build check completed"

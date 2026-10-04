
# Check if theme/json.go compiles - look for Variant issues
cd /app
go build theme/json.go 2>&1 | head -10

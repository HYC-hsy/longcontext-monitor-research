
# Check if theme/json.go compiles now
cd /app
go build theme/json.go 2>&1 | head -10

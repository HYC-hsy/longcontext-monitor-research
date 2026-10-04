
# Check if the entire codebase compiles
cd /app
go build ./... 2>&1 | grep -E "(error|testapp|Metadata)" | head -20

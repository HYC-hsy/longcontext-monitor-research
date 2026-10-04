
# Check client package structure
cd /app
ls -la client/ 2>/dev/null | head -20
find client/ -name "option*.go" 2>/dev/null

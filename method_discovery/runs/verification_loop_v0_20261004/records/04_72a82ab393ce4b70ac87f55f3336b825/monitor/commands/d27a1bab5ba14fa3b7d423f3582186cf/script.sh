
# Quick build check to see remaining errors
cd /app
go build ./... 2>&1 | grep "^#\|\.go:" | head -25
echo ""
echo "Error count:"
go build ./... 2>&1 | grep "\.go:" | wc -l


# Final build check
cd /app
echo "=== Build Errors Remaining ==="
go build ./... 2>&1 | grep "\.go:" | wc -l
echo ""
go build ./... 2>&1 | grep "^#\|\.go:" | head -15

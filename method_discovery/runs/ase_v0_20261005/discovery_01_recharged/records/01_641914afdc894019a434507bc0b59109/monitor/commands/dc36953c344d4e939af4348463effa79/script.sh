
# Run comprehensive build check
echo "=== COMPREHENSIVE BUILD CHECK ==="
cd /app && go build ./pkg/rpcinfo/... 2>&1 | head -20
echo ""
echo "---"
echo ""
cd /app && go build ./client/... 2>&1 | head -30


# Quick build test to check current status
echo "=== QUICK BUILD STATUS (Turn 217) ==="
cd /app && timeout 60 go build ./client/... ./pkg/rpcinfo/... ./pkg/endpoint/... ./pkg/streaming/... 2>&1 | head -30


# Check Target 3 protocol constants more carefully
echo "=== TARGET 3 DETAILED CHECK ==="
grep -A2 "TTHeaderStreaming\|GRPCStreaming" /app/transport/keys.go | head -15

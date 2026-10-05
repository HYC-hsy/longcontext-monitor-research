
# Check what's been added to conn_pool.go
echo "=== Checking conn_pool.go for Dump() method ==="
grep -n "func.*Dump" /app/pkg/remote/trans/nphttp2/conn_pool.go || echo "NOT YET ADDED"

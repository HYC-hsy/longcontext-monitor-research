
# Check Target 6: conn_pool.go Dump() method
cd /app && find pkg/remote/trans/nphttp2 -name "conn_pool.go" | head -1 | xargs grep -n "func.*Dump()" 2>/dev/null || echo "Dump() not found in conn_pool.go"

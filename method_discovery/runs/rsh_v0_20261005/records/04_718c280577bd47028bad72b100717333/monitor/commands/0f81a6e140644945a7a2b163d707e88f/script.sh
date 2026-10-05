
# Check if connPool.Dump() method exists and has correct signature
cd /app && grep -A 20 "func (cp \*connPool) Dump()" pkg/remote/trans/nphttp2/conn_pool.go | head -25

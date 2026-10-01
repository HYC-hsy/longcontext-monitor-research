
# Verify connPool.Dump() exists and has panic recovery
grep -A 20 "func (cp \*connPool) Dump()" /app/pkg/remote/trans/nphttp2/conn_pool.go | head -25

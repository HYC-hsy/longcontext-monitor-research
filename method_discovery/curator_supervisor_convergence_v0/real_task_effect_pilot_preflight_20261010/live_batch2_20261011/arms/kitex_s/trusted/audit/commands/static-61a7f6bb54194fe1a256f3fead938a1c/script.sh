
# Check transport package
ls -la /app/pkg/remote/trans* 2>/dev/null | head -20
echo "---"
find /app/pkg/remote -name "conn_pool.go" -o -name "frame_reader.go" 2>/dev/null


# Check if Args and Result were modified
grep -A 3 "type Args struct" /app/pkg/streaming/streaming.go
echo "---"
grep -A 3 "type Result struct" /app/pkg/streaming/streaming.go

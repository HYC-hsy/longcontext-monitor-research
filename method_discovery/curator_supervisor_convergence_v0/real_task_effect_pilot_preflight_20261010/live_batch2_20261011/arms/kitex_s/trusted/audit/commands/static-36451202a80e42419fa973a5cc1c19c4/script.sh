
# Check if Args and Result were extended with ServerStream and ClientStream fields
grep -A 5 "type Args struct" /app/pkg/streaming/streaming.go
echo "---"
grep -A 5 "type Result struct" /app/pkg/streaming/streaming.go


# Check if Args/Result were extended with ClientStream and ServerStream fields
cd /app && grep -A5 "^type Args struct" pkg/streaming/streaming.go

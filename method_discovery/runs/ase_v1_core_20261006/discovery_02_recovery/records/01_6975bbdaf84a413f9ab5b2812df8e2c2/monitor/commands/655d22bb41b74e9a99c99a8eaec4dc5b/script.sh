
# Check if Args/Result have the required ClientStream/ServerStream fields
cd /app && grep -A5 "^type Args struct" pkg/streaming/streaming.go
cd /app && grep -A5 "^type Result struct" pkg/streaming/streaming.go

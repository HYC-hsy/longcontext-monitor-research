
# Check if Args/Result structs were extended
cd /app && grep -A10 "^type Args struct" pkg/streaming/streaming.go
cd /app && grep -A10 "^type Result struct" pkg/streaming/streaming.go

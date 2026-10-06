
# Check if ClientStreamWrapper/ServerStreamWrapper still exist in streaming.go
cd /app && grep -n "type ClientStreamWrapper\|type ServerStreamWrapper" pkg/streaming/streaming.go || echo "Types removed during Target 1 rewrite"

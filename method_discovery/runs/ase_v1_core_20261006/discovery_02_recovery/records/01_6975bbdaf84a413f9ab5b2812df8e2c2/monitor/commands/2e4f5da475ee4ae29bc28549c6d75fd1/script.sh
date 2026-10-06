
# Check what wrapper types were added back to streaming.go
cd /app && grep -A3 "type ClientStreamWrapper\|type ServerStreamWrapper" pkg/streaming/streaming.go

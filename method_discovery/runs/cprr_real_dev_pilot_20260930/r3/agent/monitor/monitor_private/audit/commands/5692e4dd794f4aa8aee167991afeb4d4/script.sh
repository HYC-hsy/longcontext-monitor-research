
# Check current Target 4 marshal implementation for FastCodec/Frugal fallback
cd /app && grep -A 20 "func.*marshalThriftData" pkg/remote/codec/thrift/thrift_data.go | grep -A 15 "} else {" | head -20


# Verify Target 4 fallback includes FastCodec/Frugal
cd /app && grep -A 15 "For Basic codec" pkg/remote/codec/thrift/thrift_data.go | head -25

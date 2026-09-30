
# Check Target 4 marshal fallback also includes FastCodec/Frugal
cd /app && grep -B 5 -A 10 "marshalThriftData" pkg/remote/codec/thrift/thrift_data.go | grep -A 12 "} else {" | head -15

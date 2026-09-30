
# Check complete Target 4 implementation - both marshal and unmarshal
cd /app && git diff pkg/remote/codec/thrift/thrift_data.go | grep -E "(Basic codec|FastCodec|Frugal)" | head -20

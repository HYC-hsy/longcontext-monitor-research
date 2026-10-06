
# Check Target 4: The requirement is for Basic codec fallback, not just documentation
cd /app && grep -A20 "unmarshalThriftData.*Reader.*interface.*int" pkg/remote/codec/thrift/thrift_data.go | head -30

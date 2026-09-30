
# Check all changes to thrift codec files
cd /app && git diff pkg/remote/codec/thrift/thrift.go pkg/remote/codec/thrift/thrift_data.go | head -150

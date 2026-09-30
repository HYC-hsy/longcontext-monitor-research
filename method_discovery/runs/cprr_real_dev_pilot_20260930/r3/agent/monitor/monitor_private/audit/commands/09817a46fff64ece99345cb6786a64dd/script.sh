
# Check for changes to thrift codec files
cd /app && git diff pkg/remote/codec/thrift/thrift.go | head -80


# Check if marshal fallback was extended
cd /app && sed -n '76,85p' pkg/remote/codec/thrift/thrift_data.go

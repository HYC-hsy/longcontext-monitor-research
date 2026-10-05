
# Check if the Marshal method fallback logic was fixed for Basic codec
grep -A 20 "if user only wants to use Basic" /app/pkg/remote/codec/thrift/thrift.go

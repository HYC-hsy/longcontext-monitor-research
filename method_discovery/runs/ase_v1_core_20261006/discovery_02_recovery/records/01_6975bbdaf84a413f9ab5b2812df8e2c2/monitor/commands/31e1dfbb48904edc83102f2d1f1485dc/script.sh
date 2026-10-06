
# Check critical Target 4 issue: Does Basic codec actually get fallback?
cd /app && grep -B5 -A15 "c.CodecType == Basic" pkg/remote/codec/thrift/thrift_data.go || echo "Basic codec check not found"

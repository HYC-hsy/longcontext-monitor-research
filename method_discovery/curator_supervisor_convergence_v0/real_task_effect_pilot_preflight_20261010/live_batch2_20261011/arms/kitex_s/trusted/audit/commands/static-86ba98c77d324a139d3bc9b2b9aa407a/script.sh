
# Verify Target 4 - check if Basic codec actually has fallback
grep -A 10 "if c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go
echo "---"
echo "This shows Basic codec is EXCLUDED from fallback (line 66: if c.CodecType != Basic)"

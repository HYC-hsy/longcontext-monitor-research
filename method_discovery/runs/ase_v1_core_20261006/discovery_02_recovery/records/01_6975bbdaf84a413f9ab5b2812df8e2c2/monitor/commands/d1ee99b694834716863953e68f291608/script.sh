
# Check Target 4 critical issue
echo "=== CRITICAL TARGET 4 ISSUE ==="
echo "Current fallback code excludes Basic codec:"
grep -A10 "if c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go | head -12
echo ""
echo "SPEC REQUIRES: Basic codec MUST succeed with FastCodec/Frugal when available"
echo "CURRENT: Fallback only applies when c.CodecType != Basic (i.e., EXCLUDES Basic!)"
echo "This is backwards - Basic codec never gets fallback!"


# Verify Target 4 is still wrong - the != Basic condition still exists
echo "=== TARGET 4 CRITICAL ISSUE ==="
echo "The condition 'c.CodecType != Basic' at line 131 still EXCLUDES Basic from fallback"
echo "This means Basic codec NEVER gets fallback to FastCodec/Frugal"
echo ""
echo "Spec requirement: Basic codec MUST succeed with FastCodec/Frugal when available"
echo "Current: Only non-Basic codecs get fallback"
echo ""
echo "Context around line 131:"
sed -n '126,145p' /app/pkg/remote/codec/thrift/thrift_data.go

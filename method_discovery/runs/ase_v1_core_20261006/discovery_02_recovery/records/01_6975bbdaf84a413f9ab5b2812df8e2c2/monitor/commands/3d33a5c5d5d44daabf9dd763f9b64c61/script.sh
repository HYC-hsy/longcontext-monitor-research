
# Check Target 4 Basic codec issue - this is still critical
echo "=== TARGET 4 - STILL WRONG ==="
echo "Basic codec fallback condition at line 131:"
sed -n '126,145p' /app/pkg/remote/codec/thrift/thrift_data.go | grep -A8 "!= Basic"
echo ""
echo "This condition EXCLUDES Basic from fallback - it's backwards!"

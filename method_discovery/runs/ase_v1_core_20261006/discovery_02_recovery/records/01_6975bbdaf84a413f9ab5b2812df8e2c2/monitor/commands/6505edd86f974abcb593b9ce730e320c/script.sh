
# Check if Target 4 Basic codec issue is really still wrong
echo "=== TARGET 4 VERIFICATION ==="
echo "The '!= Basic' condition still exists, which means Basic codec is EXCLUDED from fallback:"
sed -n '126,145p' /app/pkg/remote/codec/thrift/thrift_data.go

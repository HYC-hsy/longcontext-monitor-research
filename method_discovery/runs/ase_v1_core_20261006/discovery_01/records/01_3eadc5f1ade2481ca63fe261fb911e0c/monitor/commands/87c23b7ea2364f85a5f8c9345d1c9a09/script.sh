
# Check for thrift codec
ls -la /app/pkg/remote/codec/thrift/ 2>&1 | head -20
echo "---"
# Check for internal/client
ls -la /app/internal/client/ 2>&1 | head -20
echo "---"
# Check client options structure
head -50 /app/client/option.go


# Check for the key packages/files mentioned in the 6 targets
echo "=== Target 1: pkg/streaming ==="
ls -la /app/pkg/streaming/ 2>&1 | head -10

echo -e "\n=== Target 2: pkg/endpoint ==="
ls -la /app/pkg/endpoint/ 2>&1 | head -10

echo -e "\n=== Target 3: transport package ==="
ls -la /app/transport/ 2>&1 | head -10

echo -e "\n=== Target 4: pkg/remote/codec/thrift ==="
ls -la /app/pkg/remote/codec/thrift/ 2>&1 | head -10

echo -e "\n=== Target 5: client package ==="
ls /app/client/*.go 2>&1 | head -15

echo -e "\n=== Target 6: pkg/remote/trans/nphttp2 ==="
ls -la /app/pkg/remote/trans/nphttp2/ 2>&1 | head -10

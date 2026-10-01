
# Check key directories from the task
echo "=== pkg/streaming ==="
ls -la /app/pkg/streaming/ 2>&1 | head -20

echo -e "\n=== pkg/endpoint ==="
ls -la /app/pkg/endpoint/ 2>&1 | head -20

echo -e "\n=== client directory ==="
ls -la /app/client/ 2>&1 | head -20

echo -e "\n=== transport ==="
ls -la /app/transport/ 2>&1 | head -10

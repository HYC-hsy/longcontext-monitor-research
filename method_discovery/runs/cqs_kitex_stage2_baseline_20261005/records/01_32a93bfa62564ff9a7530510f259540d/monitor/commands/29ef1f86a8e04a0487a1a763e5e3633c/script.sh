
# Check what exists in pkg/streaming
ls -la /app/pkg/streaming/ 2>&1 | head -20

# Check what exists in pkg/endpoint  
echo "--- pkg/endpoint ---"
ls -la /app/pkg/endpoint/ 2>&1 | head -20

# Check client package
echo "--- client ---"
ls -la /app/client/ 2>&1 | head -10

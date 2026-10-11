
# Check if there's a pkg/transport directory
ls -la /app/pkg/ | grep transport
echo "---"
# Or maybe internal/transport
ls -la /app/internal/ 2>/dev/null | grep transport

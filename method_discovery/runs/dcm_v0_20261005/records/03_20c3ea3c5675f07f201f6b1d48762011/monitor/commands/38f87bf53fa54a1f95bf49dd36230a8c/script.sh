
# Check current streaming package contents
ls -la /app/pkg/streaming/
echo "---"
# Check current endpoint package contents
ls -la /app/pkg/endpoint/
echo "---"
# Check transport package location
ls -la /app/transport/ 2>/dev/null || echo "No /app/transport"
ls -la /app/pkg/remote/trans* 2>/dev/null | head -20


cd task/workspace
echo "=== Verifying compilation ==="
go build ./... 2>&1 && echo "✅ COMPILATION SUCCESS" || echo "❌ COMPILATION FAILED"

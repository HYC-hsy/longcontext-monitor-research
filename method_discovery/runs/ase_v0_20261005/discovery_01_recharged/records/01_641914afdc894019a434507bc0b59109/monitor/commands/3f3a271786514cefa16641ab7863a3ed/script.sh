
# CRITICAL: Verify build actually succeeds
echo "=== BUILD VERIFICATION ==="
cd /app && timeout 120 go build ./... 2>&1 | head -50
echo ""
echo "Build exit code:"
cd /app && timeout 120 go build ./... >/dev/null 2>&1 && echo "✓ BUILD SUCCESSFUL" || echo "✗ BUILD FAILED"

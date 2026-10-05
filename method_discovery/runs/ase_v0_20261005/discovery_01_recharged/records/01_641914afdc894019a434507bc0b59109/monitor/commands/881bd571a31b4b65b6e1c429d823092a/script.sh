
# Check what streamx types actually exist
echo "=== STREAMX PACKAGE TYPE VERIFICATION ==="
echo ""
echo "Checking pkg/streamx types:"
grep "^type" /app/pkg/streamx/*.go 2>/dev/null | head -20
echo ""
echo "Checking internal/streamx types:"
grep "^type" /app/internal/streamx/*.go 2>/dev/null | head -20

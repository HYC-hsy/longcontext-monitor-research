
# Check what functions are in the new option files
echo "=== option_unary.go ==="
grep "^func " /app/client/option_unary.go 2>/dev/null | head -10
echo ""
echo "=== option_stream.go ==="
grep "^func " /app/client/option_stream.go 2>/dev/null | head -15
echo ""
echo "=== option_ttstream.go ==="
grep "^func " /app/client/option_ttstream.go 2>/dev/null | head -10

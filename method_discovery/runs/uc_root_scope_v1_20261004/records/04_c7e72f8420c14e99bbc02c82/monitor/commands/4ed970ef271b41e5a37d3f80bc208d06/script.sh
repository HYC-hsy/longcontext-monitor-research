
# Check what functions are actually in the Target 5 option files
echo "=== client/option.go ==="
grep "^func\|^type" /app/client/option.go 2>/dev/null | head -20

echo -e "\n=== client/option_unary.go ==="
grep "^func" /app/client/option_unary.go 2>/dev/null | head -10

echo -e "\n=== client/option_stream.go ==="
grep "^func" /app/client/option_stream.go 2>/dev/null | head -10

echo -e "\n=== client/option_ttstream.go ==="
grep "^func" /app/client/option_ttstream.go 2>/dev/null | head -10

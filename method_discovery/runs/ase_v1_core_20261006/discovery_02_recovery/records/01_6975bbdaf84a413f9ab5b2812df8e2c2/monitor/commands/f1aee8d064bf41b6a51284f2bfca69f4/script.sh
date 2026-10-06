
# Check if conversion helpers were added
echo "=== CONVERSION HELPERS CHECK ==="
grep -c "func.*ToMD\|func.*ToHeader\|func.*ToTrailer" /app/pkg/streaming/streaming.go
grep "func.*ToMD\|func.*ToHeader\|func.*ToTrailer" /app/pkg/streaming/streaming.go | head -6

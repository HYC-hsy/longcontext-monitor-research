
# Check if there's ALSO fallback logic that INCLUDES Basic
echo "=== CHECKING IF BASIC CODEC GETS FALLBACK ELSEWHERE ==="
grep -B5 -A15 "typecodec.Apache.*false" /app/pkg/remote/codec/thrift/thrift_data.go | head -25

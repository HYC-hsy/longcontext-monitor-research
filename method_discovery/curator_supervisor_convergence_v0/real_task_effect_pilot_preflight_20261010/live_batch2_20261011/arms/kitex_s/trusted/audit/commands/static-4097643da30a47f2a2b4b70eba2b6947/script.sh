
# Check what Target 3 String() implementation looks like
echo "=== Checking Protocol String() method in transport/keys.go ==="
grep -A 40 "func.*Protocol.*String" /app/transport/keys.go | head -45

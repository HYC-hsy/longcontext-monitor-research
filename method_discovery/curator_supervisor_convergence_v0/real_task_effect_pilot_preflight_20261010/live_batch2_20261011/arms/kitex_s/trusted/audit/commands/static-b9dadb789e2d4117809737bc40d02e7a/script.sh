
# Check the current Protocol String() implementation
echo "=== Current Protocol String() implementation (still wrong - just switch cases) ==="
grep -A 25 "func.*Protocol.*String" /app/transport/keys.go | head -30


# Check if the type aliases in option.go are correct (should be aliases, not new types)
echo "=== Checking Type Aliases in client/option.go ==="
grep -A2 "^type UnaryOption\|^type StreamOption\|^type TTHeaderStreamingOption" /app/client/option.go | head -20

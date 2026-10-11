
# Check how UnaryOption/StreamOption/TTHeaderStreamingOption are defined in client package
echo "=== Type definitions in option_categories.go ==="
grep -A 3 "^type UnaryOption\|^type StreamOption\|^type TTHeaderStreamingOption" /app/client/option_categories.go 2>/dev/null | head -15
echo ""
# The task requires type ALIASES like: UnaryOption = client.UnaryOption (alias to internal/client.UnaryOption)
# Not wrapper structs

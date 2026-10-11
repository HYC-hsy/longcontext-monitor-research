
# Check if the 4 required files exist for Target 5
echo "=== Checking Target 5 File Structure ==="
for file in option.go option_unary.go option_stream.go option_ttstream.go; do
    if [ -f "/app/client/$file" ]; then
        echo "✓ client/$file exists"
    else
        echo "✗ client/$file MISSING"
    fi
done

echo ""
echo "=== Checking for type aliases in option.go ==="
grep -n "type UnaryOption\|type StreamOption\|type TTHeaderStreamingOption\|func TailOption" /app/client/option.go | head -10 || echo "Type aliases not found"

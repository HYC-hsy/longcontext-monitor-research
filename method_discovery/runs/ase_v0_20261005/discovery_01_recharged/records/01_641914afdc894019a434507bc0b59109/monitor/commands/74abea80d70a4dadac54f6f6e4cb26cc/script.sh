
# Check what option files exist and their basic structure
echo "=== Checking client option files ==="
for file in /app/client/option_unary.go /app/client/option_stream.go /app/client/option_ttstream.go; do
  if [ -f "$file" ]; then
    echo "✓ Found: $file"
    grep -E "^func With" "$file" | head -5
  else
    echo "✗ Missing: $file"
  fi
  echo ""
done

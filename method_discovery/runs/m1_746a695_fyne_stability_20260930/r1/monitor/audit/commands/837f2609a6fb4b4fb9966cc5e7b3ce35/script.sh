
# Check if theme JSON support exists
ls -la /app/theme/ 2>/dev/null | grep -i json || echo "No JSON-related theme files found"

# Check if binding sprintf exists
ls -la /app/data/binding/ 2>/dev/null | grep sprintf || echo "No sprintf binding file found"

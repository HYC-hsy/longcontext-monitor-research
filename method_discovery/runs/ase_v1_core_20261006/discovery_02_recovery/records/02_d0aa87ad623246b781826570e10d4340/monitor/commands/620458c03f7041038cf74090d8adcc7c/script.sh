
# Check if Shortcut interface exists and its definition
grep -r "type Shortcut interface" /app/*.go 2>/dev/null || echo "Not found in root"
grep -r "type.*Shortcut.*interface" /app/*.go | head -5

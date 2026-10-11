
# Search for Protocol type more broadly
grep -rn "^type Protocol " /app/pkg/ 2>/dev/null | grep -v "Info\|Error" | head -5

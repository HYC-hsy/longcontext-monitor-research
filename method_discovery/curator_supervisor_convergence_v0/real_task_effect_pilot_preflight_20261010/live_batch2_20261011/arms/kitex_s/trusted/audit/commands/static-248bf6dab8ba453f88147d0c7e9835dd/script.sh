
# Search for where TTHeader and Framed constants might be defined
grep -rn "TTHeader.*=" /app/pkg/ 2>/dev/null | grep -v "test\|//" | head -10

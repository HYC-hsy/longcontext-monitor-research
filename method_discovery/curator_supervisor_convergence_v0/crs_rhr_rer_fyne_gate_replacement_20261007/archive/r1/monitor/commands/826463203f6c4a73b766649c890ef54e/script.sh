
cd /app/data/binding
grep -l "StringToStringWithFormat" *.go 2>/dev/null || echo "Not found in any .go file"

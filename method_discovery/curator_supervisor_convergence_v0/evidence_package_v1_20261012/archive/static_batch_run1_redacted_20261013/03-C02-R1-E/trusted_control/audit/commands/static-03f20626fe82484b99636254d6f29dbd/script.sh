
# Check if Bytes and URI types are handled in NewSprintf - look for the spec requirement
cd /app && grep -n "Bytes\|Rune\|URI" data/binding/sprintf.go | head -20

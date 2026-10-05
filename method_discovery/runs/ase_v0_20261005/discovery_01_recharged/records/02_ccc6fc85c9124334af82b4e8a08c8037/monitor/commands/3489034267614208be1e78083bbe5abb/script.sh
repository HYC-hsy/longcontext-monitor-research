
# Check what base binding types exist and how they should be initialized
grep -A 5 "type base struct" /app/data/binding/*.go 2>/dev/null | head -20
grep -n "ExtendBase\|NewBase" /app/data/binding/*.go 2>/dev/null | head -10

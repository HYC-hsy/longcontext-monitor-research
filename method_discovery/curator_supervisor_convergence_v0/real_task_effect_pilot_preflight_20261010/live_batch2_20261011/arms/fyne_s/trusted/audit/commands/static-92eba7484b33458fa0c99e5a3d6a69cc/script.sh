
cd task/workspace
# Check if Bytes and Rune binding types exist
grep -r "type.*Bytes.*interface" data/binding/ | head -5
grep -r "type.*Rune.*interface" data/binding/ | head -5

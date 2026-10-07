
cd /app && grep -n "type.*Bytes.*interface\|type.*Rune.*interface\|type.*URI.*interface" data/binding/*.go | grep -v "^Binary"

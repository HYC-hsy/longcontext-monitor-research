
# Check if Bytes, Rune, URI types exist in the binding package
cd /app && grep -n "^type Bytes interface\|^type Rune interface\|^type URI interface" data/binding/*.go

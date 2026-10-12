
# Check if Rune is handled in Get() - the spec mentions Rune as a supported type
cd /app && grep -n "case Rune" data/binding/sprintf.go

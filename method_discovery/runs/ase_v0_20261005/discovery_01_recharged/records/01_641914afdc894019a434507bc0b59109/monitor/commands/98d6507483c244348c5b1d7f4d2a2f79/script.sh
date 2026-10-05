
# Check the StreamOption type declarations
echo "=== STREAMOPTION TYPE DUPLICATION CHECK ==="
echo ""
echo "In client/option.go (line 59):"
sed -n '59,60p' /app/client/option.go
echo ""
echo "In client/option_stream.go (line 29):"
sed -n '29,30p' /app/client/option_stream.go
echo ""
echo "ANALYSIS:"
echo "  StreamOption type is already defined in option.go"
echo "  option_stream.go should NOT redeclare it, just use it"
echo "  This is a simple fix: remove the duplicate type declaration"

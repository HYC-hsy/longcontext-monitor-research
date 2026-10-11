
# Critical behavioral verification: Hyperlink.Tapped must check OnTapped callback
echo "=== Searching for Hyperlink Tapped/tapped methods ==="
grep -n "func.*Hyperlink.*[Tt]apped" widget/hyperlink.go
echo ""

# Try different patterns to find the tap handling
echo "=== Searching for Hyperlink tap/open URL implementation ==="
grep -n "openURL\|Open.*URL\|launcher" widget/hyperlink.go | head -10
echo ""

# Look at the full hyperlink.go file structure
echo "=== Hyperlink file method list ==="
grep "^func (h \*Hyperlink)" widget/hyperlink.go

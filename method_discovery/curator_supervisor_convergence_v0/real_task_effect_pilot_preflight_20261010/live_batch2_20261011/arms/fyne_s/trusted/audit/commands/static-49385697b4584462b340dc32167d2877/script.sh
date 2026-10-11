
cd /app

echo "=== Hyperlink OnTapped Implementation Analysis ==="
echo
echo "1. Hyperlink struct definition (showing OnTapped field):"
grep -A 15 "^type Hyperlink struct" widget/hyperlink.go
echo
echo "2. Tapped() method implementation:"
grep -A 3 "^func (hl \*Hyperlink) Tapped" widget/hyperlink.go
echo
echo "3. openURL() method implementation:"
grep -A 10 "^func (hl \*Hyperlink) openURL" widget/hyperlink.go
echo
echo "4. TypedKey Space handler (also triggers action):"
grep -A 5 "if ev.Name == fyne.KeySpace" widget/hyperlink.go

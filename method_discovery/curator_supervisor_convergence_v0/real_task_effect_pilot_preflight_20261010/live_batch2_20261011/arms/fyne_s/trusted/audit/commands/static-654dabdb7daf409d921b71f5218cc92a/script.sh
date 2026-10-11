
cd /app

echo "=== Behavioral Implementation Verification ==="
echo
echo "1. Container.RemoveAll implementation:"
grep -A 5 "func (c \*Container) RemoveAll()" container.go
echo
echo "2. Hyperlink.Tapped() - checking OnTapped callback usage:"
grep -B 2 -A 10 "func (hl \*Hyperlink) Tapped" widget/hyperlink.go
echo
echo "3. Entry.SetMinRowsVisible and MinSize interaction:"
grep -A 5 "func (e \*Entry) SetMinRowsVisible" widget/entry.go
grep "MinRowsVisible" widget/entry.go | head -5

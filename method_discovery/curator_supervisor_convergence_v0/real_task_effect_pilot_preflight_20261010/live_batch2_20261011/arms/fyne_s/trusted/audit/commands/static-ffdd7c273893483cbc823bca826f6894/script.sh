
# Verify behavioral implementations that compilation alone cannot prove

echo "=== Target 6: Container.Add nil-safe check ==="
sed -n '/^func (c \*Container) Add/,/^}/p' container.go
echo ""

echo "=== Target 3: NewSprintf DataChanged listener registration ==="
sed -n '/^func NewSprintf/,/^}/p' data/binding/sprintf.go | head -60
echo ""

echo "=== Target 6: Hyperlink.Tapped checking OnTapped callback ==="
sed -n '/^func (h \*Hyperlink) Tapped/,/^}/p' widget/hyperlink.go
echo ""

echo "=== Target 6: Entry.MinSize using MinRowsVisible ==="
grep -A 20 "func (e \*Entry) MinSize()" widget/entry.go | grep -B 5 -A 5 "MinRowsVisible"

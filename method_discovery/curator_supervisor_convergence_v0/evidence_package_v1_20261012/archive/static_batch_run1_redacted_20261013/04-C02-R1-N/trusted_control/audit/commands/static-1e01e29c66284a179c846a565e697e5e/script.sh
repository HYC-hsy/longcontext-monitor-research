
# Check Hyperlink.Tapped behavior - does OnTapped replace or supplement URL opening?
cd /app && grep -A 15 "func (hl \*Hyperlink) Tapped" widget/hyperlink.go

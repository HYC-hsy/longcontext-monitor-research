
# Check if Hyperlink.OnTapped overrides URL opening behavior
cd /app && grep -A 15 "func (h \*Hyperlink) Tapped" widget/hyperlink.go

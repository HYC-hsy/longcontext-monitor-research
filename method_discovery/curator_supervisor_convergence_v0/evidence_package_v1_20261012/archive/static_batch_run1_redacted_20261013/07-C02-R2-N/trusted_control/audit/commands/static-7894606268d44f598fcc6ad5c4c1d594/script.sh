
# Verify the spec requirement for Hyperlink.OnTapped behavior
cd /app && grep -A 20 "func (h \*Hyperlink) Tapped" widget/hyperlink.go | head -25

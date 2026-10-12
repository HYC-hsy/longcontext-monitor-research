
# Check the openURL method to understand what Tapped is calling
cd /app && grep -A 8 "func (hl \*Hyperlink) openURL" widget/hyperlink.go

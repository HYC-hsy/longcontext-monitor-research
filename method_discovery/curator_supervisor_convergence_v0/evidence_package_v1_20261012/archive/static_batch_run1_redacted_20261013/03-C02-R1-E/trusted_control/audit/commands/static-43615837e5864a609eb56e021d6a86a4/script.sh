
# Check if OnTapped is actually implemented in the openURL or Tapped methods
cd /app && grep -B 5 -A 15 "func (hl \*Hyperlink) openURL" widget/hyperlink.go

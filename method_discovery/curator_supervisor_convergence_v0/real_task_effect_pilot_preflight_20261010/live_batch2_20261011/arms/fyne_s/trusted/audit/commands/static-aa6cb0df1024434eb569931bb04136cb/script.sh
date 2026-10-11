
# Check Hyperlink.OnTapped callback override (Target 6 behavioral requirement)
cd /app/widget
grep -B 2 -A 10 "func (h \*Hyperlink) openURL()" hyperlink.go | head -15

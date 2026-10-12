
# Need to check if openURL is called when OnTapped is set - search for the check
cd /app && grep -B 10 -A 5 "func (hl \*Hyperlink) openURL" widget/hyperlink.go


# Check if fyneApp has Metadata() method
grep -n "func (a \*fyneApp) Metadata()" /app/app/app.go

# Also check the general structure
grep -n "type fyneApp struct" /app/app/app.go -A 5

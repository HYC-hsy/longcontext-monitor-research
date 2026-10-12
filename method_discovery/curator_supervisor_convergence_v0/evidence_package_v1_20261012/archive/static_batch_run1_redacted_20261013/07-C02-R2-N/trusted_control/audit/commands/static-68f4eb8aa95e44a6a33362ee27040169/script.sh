
# Check if fyneApp has Metadata() method
cd /app && grep -A 5 "func (a \*fyneApp) Metadata" app/app.go

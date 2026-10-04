
# Check if validation.NewAllStrings file exists now
cd /app
ls -la data/validation/all.go 2>&1 && grep -n "func NewAllStrings" data/validation/all.go 2>&1 | head -5

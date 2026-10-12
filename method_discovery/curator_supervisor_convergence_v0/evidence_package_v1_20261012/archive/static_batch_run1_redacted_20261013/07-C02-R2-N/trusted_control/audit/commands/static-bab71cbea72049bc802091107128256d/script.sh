
# Check for validation.NewAllStrings in correct location
cd /app && ls -la data/validation/all.go 2>&1 && grep -A 15 "func NewAllStrings" data/validation/all.go 2>&1

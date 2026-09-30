
# Check if validation.NewAllStrings exists
ls -la /app/data/validation/all.go 2>&1 || echo "all.go does not exist"

# Search for NewAllStrings function
grep -rn "NewAllStrings" /app/data/validation/ 2>&1 || echo "NewAllStrings not found in validation package"

# List what exists in validation package
ls -la /app/data/validation/*.go


# Check container.go for RemoveAll method
grep -n "RemoveAll" /app/container.go

# Check widget/toolbar.go for SetIcon and return types
ls -la /app/widget/toolbar.go 2>&1 || echo "toolbar.go does not exist"

# Check for theme JSON support
ls -la /app/theme/*.go 2>&1 | head -20

# Check data/binding for sprintf
ls -la /app/data/binding/*.go 2>&1 | head -20

# Check data/validation for all.go
ls -la /app/data/validation/*.go 2>&1


# Help identify the correct ThemeVariant constants
grep -A20 "type ThemeVariant" /app/theme.go
echo "---"
# Check theme package for variant constants
grep -rn "const.*Variant" /app/theme/*.go | head -10

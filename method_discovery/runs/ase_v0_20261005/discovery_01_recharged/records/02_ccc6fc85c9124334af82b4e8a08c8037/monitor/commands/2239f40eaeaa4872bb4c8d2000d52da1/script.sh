
# Check what theme variant constants exist
grep -r "VariantDark\|VariantLight\|ThemeVariant" /app/*.go /app/theme/*.go 2>/dev/null | grep -v ".git" | head -20

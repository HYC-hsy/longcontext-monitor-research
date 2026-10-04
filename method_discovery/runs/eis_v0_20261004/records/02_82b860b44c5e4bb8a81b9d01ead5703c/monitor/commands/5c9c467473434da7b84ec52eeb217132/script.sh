
# Verify all.go exists and contains NewAllStrings
ls -la /app/data/validation/all.go 2>&1
grep -n "NewAllStrings" /app/data/validation/all.go

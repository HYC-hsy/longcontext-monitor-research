
# Verify Target 6 - NewAllStrings validator
cd /app
grep -A10 "func NewAllStrings" data/validation/allstrings.go 2>&1

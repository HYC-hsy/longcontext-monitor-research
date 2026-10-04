
# Verify Target 6 - NewAllStrings signature (must chain validators, not whitelist strings)
cd /app
echo "=== Target 6: NewAllStrings Signature ===" && \
grep -B2 -A15 "func NewAllStrings" data/validation/allstrings.go


# Check transport protocol constants
cd /app
grep -r "type Protocol" transport/ pkg/remote/trans* 2>/dev/null | head -5

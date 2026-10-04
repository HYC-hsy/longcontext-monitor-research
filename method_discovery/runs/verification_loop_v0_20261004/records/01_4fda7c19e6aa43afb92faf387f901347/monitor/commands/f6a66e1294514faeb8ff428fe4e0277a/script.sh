
# Check what methods App interface actually requires
cd /app
grep -A 50 "^type App interface" app.go | grep "^\t[A-Z]" | head -20

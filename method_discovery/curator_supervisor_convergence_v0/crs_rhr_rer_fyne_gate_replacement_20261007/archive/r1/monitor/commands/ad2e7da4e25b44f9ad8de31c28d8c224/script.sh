
cd /app/data/binding
# Find type declarations in the binding package
grep -n "^type.*interface" binditems.go | head -10

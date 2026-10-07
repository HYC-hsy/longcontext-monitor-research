
cd /app/data/binding
# Check what binding types are defined
grep "^type [A-Z].*interface" *.go | grep -v "test"


# Check if Bytes type exists in binding package
cd /app && grep -n "^type Bytes interface" data/binding/*.go

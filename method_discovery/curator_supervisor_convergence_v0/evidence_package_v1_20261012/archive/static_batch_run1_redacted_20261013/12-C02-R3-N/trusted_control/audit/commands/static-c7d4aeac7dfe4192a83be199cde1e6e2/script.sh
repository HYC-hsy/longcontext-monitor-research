
# Check if Bytes and URI handling exists in sprintf Set method
cd /app && grep -C 5 "Bytes\|URI" data/binding/sprintf.go | grep -A 5 "case.*Bytes\|case.*URI"

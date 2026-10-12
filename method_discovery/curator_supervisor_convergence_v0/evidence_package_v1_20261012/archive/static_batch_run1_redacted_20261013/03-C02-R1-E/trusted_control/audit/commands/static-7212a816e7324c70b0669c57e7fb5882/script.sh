
# Verify that sprintf.go handles Bytes and URI correctly in Set()
cd /app && grep -B 5 -A 20 "case Bytes:" data/binding/sprintf.go

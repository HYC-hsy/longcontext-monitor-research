
# Check if NewSprintf handles Bytes and URI specially in Set()
cd /app && grep -A 100 "func (b \*sprintfBinding) Set" data/binding/sprintf.go | grep -A 5 -B 5 "Bytes\|URI\|storage.ParseURI"

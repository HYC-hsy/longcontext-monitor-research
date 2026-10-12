
# Check Bytes and URI handling in Set() method - look for special handling
cd /app && grep -A100 "func (b \*sprintfBinding) Set" data/binding/sprintf.go | grep -A5 -B5 "Bytes\|URI"

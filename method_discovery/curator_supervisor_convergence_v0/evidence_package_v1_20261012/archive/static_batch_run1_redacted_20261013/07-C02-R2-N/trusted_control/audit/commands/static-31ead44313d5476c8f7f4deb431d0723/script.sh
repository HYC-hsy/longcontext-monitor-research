
# Check for Set() method in sprintf.go
cd /app && grep -A 20 "func (b \*sprintfBinding) Set" data/binding/sprintf.go

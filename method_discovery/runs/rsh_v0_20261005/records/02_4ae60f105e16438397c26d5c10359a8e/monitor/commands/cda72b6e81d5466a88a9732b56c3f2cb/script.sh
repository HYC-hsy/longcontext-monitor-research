
# Check if sprintf.go has been modified recently and check its Set() method
grep -A 10 "func (s \*sprintfBinding) Set" /app/data/binding/sprintf.go


# Look for the full Get() method to see all type handling
cd /app && sed -n '/^func (b \*sprintfBinding) Get/,/^}/p' data/binding/sprintf.go | head -60

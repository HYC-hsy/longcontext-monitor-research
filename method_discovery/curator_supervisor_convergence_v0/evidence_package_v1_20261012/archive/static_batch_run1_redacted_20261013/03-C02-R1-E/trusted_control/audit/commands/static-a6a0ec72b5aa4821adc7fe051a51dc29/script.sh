
# Look at the Get() method to see what binding types are handled
cd /app && sed -n '/^func (b \*sprintfBinding) Get/,/^}/p' data/binding/sprintf.go

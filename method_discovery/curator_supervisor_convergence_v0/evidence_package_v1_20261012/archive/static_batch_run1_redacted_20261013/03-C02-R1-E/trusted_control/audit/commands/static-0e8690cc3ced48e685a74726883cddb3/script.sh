
# Look at the complete Set() implementation to see what types are handled
cd /app && sed -n '/^func (b \*sprintfBinding) Set/,/^}/p' data/binding/sprintf.go | head -80


# Verify the actual NewSprintf Get() implementation handles Bytes, Rune, URI types
cd /app && sed -n '/^func (b \*sprintfBinding) Get/,/^}/p' data/binding/sprintf.go

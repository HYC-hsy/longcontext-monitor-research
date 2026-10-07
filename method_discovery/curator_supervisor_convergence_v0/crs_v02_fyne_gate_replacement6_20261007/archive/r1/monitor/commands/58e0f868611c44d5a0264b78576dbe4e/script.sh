
cd /app && sed -n '/^func (s \*stringFormat) Set/,/^}/p' data/binding/sprintf.go | head -30

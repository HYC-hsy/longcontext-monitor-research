
# Look for how other String bindings are structured
grep -B 5 -A 15 "type.*String.*struct" /app/data/binding/binditems.go 2>/dev/null | head -40

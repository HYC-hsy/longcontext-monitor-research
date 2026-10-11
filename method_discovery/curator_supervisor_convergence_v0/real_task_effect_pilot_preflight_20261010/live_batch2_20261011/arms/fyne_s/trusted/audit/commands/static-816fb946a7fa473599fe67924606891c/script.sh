
grep -n "^type.*interface {" task/workspace/data/binding/binditems.go | grep -E "(Bytes|Rune)" | head -10

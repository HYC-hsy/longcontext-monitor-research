
# Search for all interface definitions in binditems.go to find what binding types exist
grep -n "^type [A-Z].* interface {" task/workspace/data/binding/binditems.go

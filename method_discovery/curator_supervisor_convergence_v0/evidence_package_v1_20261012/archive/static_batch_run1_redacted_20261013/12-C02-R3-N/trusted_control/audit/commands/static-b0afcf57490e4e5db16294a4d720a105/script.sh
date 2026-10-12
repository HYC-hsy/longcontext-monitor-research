
# Check if StringToStringWithFormat has the "%s" optimization
cd /app && grep -B 5 "func StringToStringWithFormat" data/binding/sprintf.go | head -20

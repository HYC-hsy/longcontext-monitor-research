
# Check if StringToStringWithFormat has the %s identity optimization
cd /app && grep -A 20 "func StringToStringWithFormat" data/binding/sprintf.go | head -25

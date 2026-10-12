
# Check if Rune type is mentioned in the task spec - verify DataItem types
cd /app && grep -r "type.*Rune.*interface" data/binding/ | head -5

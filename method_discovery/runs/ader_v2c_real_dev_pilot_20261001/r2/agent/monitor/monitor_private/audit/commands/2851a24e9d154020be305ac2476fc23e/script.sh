
# Check option.go for type aliases and TailOption
grep -n "type.*Option.*=" /app/client/option.go | grep -E "(UnaryOption|StreamOption|TTHeaderStreamingOption)" | head -10
grep -n "TailOption" /app/client/option.go | head -5

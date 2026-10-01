
# Check if EqualsTo methods were added
echo "=== Checking for EqualsTo methods in cep.go ==="
grep -A5 "func.*EqualsTo" /app/pkg/endpoint/cep/cep.go

echo -e "\n=== Checking for EqualsTo methods in sep.go ==="
grep -A5 "func.*EqualsTo" /app/pkg/endpoint/sep/sep.go

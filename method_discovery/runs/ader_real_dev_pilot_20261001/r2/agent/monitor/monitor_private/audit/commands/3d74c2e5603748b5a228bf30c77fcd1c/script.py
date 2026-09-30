
# Check for DummyDummyMiddleware and EqualsTo in cep
import subprocess
result = subprocess.run(['grep', '-n', 'DummyDummy', '/app/pkg/endpoint/cep/stream_endpoint.go'], 
                       capture_output=True, text=True)
print("DummyDummyMiddleware in cep:")
print(result.stdout if result.stdout else "NOT FOUND")

result2 = subprocess.run(['grep', '-n', 'EqualsTo', '/app/pkg/endpoint/cep/stream_endpoint.go'], 
                        capture_output=True, text=True)
print("\nEqualsTo in cep:")
print(result2.stdout if result2.stdout else "NOT FOUND")


# Check if underlying types were added to internal/client/option.go
import subprocess

result = subprocess.run(['grep', '-n', 'type UnaryOptions\\|type StreamOptions\\|type TTHeaderStreamingOptions\\|type UnaryOption\\|type StreamOption\\|type TTHeaderStreamingOption', 
                        '/app/internal/client/option.go'], 
                       capture_output=True, text=True)
print("=== Option types in internal/client/option.go ===")
print(result.stdout if result.stdout else "Not found")

# Check if Options struct has new fields
result2 = subprocess.run(['grep', '-n', 'UnaryOptions\\|StreamOptions\\|TTHeaderStreamingOptions', 
                         '/app/internal/client/option.go'], 
                        capture_output=True, text=True)
print("\n=== References to new option structs ===")
print(result2.stdout[:800] if result2.stdout else "Not found")


# Search for UnaryOption, StreamOption, TTHeaderStreamingOption in option.go
import subprocess
result = subprocess.run(['grep', '-n', 'UnaryOption\\|StreamOption\\|TTHeaderStreamingOption\\|TailOption', 
                        '/app/client/option.go'], 
                       capture_output=True, text=True)
print("Searching for type aliases in option.go:")
print(result.stdout if result.stdout else "Not found")


import subprocess

print("=== Spot checking other targets ===\n")

# Target 1: App.Metadata() method
result = subprocess.run(['grep', '-n', 'Metadata() AppMetadata', '/app/app.go'], 
                       capture_output=True, text=True)
print("Target 1 - App.Metadata():")
print(result.stdout if result.stdout else "NOT FOUND")

# Target 2: theme.FromJSON
result = subprocess.run(['grep', '-n', 'func FromJSON', '/app/theme/json.go'], 
                       capture_output=True, text=True)
print("\nTarget 2 - theme.FromJSON:")
print(result.stdout if result.stdout else "NOT FOUND")

# Target 6: Container.RemoveAll
result = subprocess.run(['grep', '-n', 'func.*Container.*RemoveAll', '/app/container.go'], 
                       capture_output=True, text=True)
print("\nTarget 6a - Container.RemoveAll():")
print(result.stdout if result.stdout else "NOT FOUND")

# Target 6: Entry.SetMinRowsVisible
result = subprocess.run(['grep', '-n', 'func.*Entry.*SetMinRowsVisible', '/app/widget/entry.go'], 
                       capture_output=True, text=True)
print("\nTarget 6b - Entry.SetMinRowsVisible():")
print(result.stdout if result.stdout else "NOT FOUND")

# Target 6: validation.NewAllStrings
result = subprocess.run(['grep', '-n', 'func NewAllStrings', '/app/data/validation/all.go'], 
                       capture_output=True, text=True)
print("\nTarget 6c - validation.NewAllStrings():")
print(result.stdout if result.stdout else "NOT FOUND")

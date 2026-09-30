
import os

# Check for protocol-related files
for root, dirs, files in os.walk('/app'):
    for f in files:
        if 'protocol' in f.lower() and f.endswith('.go'):
            print(os.path.join(root, f))

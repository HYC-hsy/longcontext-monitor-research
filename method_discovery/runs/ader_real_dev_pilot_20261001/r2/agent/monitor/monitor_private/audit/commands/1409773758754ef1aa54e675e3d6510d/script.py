
import os
import time

# Check for recently modified files in key locations
paths_to_check = [
    '/app/pkg/streaming',
    '/app/pkg/endpoint/cep',
    '/app/pkg/endpoint/sep', 
    '/app/pkg/endpoint',
    '/app/transport',
    '/app/client'
]

print("Checking for new or recently modified files...")
for base_path in paths_to_check:
    if not os.path.exists(base_path):
        print(f"\n{base_path}: DOES NOT EXIST")
        continue
    
    print(f"\n{base_path}:")
    try:
        for item in sorted(os.listdir(base_path)):
            if item.endswith('.go'):
                item_path = os.path.join(base_path, item)
                mtime = os.path.getmtime(item_path)
                # Files modified in last hour (task started recently)
                age = time.time() - mtime
                if age < 3600:
                    print(f"  {item} (modified {int(age)}s ago)")
                else:
                    print(f"  {item}")
    except NotADirectoryError:
        print(f"  (not a directory)")


import os
import time

# Check for any recent modifications that might indicate work has started
recent_files = []
now = time.time()
one_hour_ago = now - 3600

for root, dirs, files in os.walk('/app'):
    # Skip deep nesting and vendor/test directories
    if root.count('/') > 5 or 'vendor' in root or '.git' in root:
        continue
    for f in files:
        if f.endswith('.go'):
            fpath = os.path.join(root, f)
            try:
                mtime = os.path.getmtime(fpath)
                if mtime > one_hour_ago:
                    recent_files.append((fpath, mtime))
            except:
                pass

recent_files.sort(key=lambda x: x[1], reverse=True)
print(f"Recently modified .go files (last hour): {len(recent_files)}")
for fpath, mtime in recent_files[:15]:
    print(f"  {fpath}")

# Check if new target directories exist
new_dirs = [
    '/app/pkg/endpoint/cep',
    '/app/pkg/endpoint/sep',
    '/app/client/option_unary.go',
    '/app/client/option_stream.go',
    '/app/client/option_ttstream.go',
]

print("\nChecking for new target files/dirs:")
for path in new_dirs:
    exists = os.path.exists(path)
    print(f"  {path}: {'EXISTS' if exists else 'NOT FOUND'}")

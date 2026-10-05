
import os
import json

# Map the directory structure
def explore_structure(base_path, max_depth=3):
    structure = {}
    
    for root, dirs, files in os.walk(base_path):
        depth = root.replace(base_path, '').count(os.sep)
        if depth >= max_depth:
            dirs[:] = []
            continue
        
        rel_path = os.path.relpath(root, base_path)
        if rel_path == '.':
            rel_path = 'root'
        
        # Filter out common non-code directories
        dirs[:] = [d for d in dirs if d not in ['.git', 'vendor', 'node_modules', '.idea']]
        
        go_files = [f for f in files if f.endswith('.go') and not f.endswith('_test.go')]
        test_files = [f for f in files if f.endswith('_test.go')]
        
        if go_files or test_files:
            structure[rel_path] = {
                'go_files': len(go_files),
                'test_files': len(test_files),
                'subdirs': sorted(dirs)
            }
    
    return structure

structure = explore_structure('/app', max_depth=4)

# Show key packages mentioned in the task
key_packages = [
    'pkg/streaming',
    'pkg/endpoint',
    'pkg/endpoint/cep', 
    'pkg/endpoint/sep',
    'transport',
    'pkg/remote/codec/thrift',
    'pkg/remote/trans/nphttp2',
    'client',
    'client/callopt'
]

print("=== Key Packages Status ===")
for pkg in key_packages:
    pkg_path = pkg if pkg.startswith('pkg/') or pkg in ['client', 'transport'] else pkg
    exists = any(pkg_path in path for path in structure.keys())
    print(f"{pkg}: {'EXISTS' if exists else 'MISSING'}")

print("\n=== Existing Structure (pkg/) ===")
for path in sorted(structure.keys()):
    if 'pkg/' in path or path == 'root':
        info = structure[path]
        print(f"{path}: {info['go_files']} go files, {info['test_files']} tests")
        if info['subdirs']:
            print(f"  subdirs: {', '.join(info['subdirs'][:5])}")

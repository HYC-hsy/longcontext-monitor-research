
import os
import json

# Get directory structure
def get_structure(path, max_depth=3, current_depth=0):
    items = []
    if current_depth >= max_depth:
        return items
    
    try:
        for item in sorted(os.listdir(path)):
            if item.startswith('.'):
                continue
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                items.append(f"{'  ' * current_depth}{item}/")
                items.extend(get_structure(item_path, max_depth, current_depth + 1))
    except PermissionError:
        pass
    return items

structure = get_structure('/app', max_depth=2)
print('\n'.join(structure[:50]))

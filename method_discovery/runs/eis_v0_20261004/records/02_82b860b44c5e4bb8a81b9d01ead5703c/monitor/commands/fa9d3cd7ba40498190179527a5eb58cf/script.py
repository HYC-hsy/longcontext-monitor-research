
# Check for key directories and files related to the task targets
import os
import json

dirs_to_check = [
    '/app/app',
    '/app/theme',
    '/app/data/binding',
    '/app/data/validation',
    '/app/widget',
    '/app/driver/desktop'
]

files_to_check = [
    '/app/app.go',
    '/app/menu.go',
    '/app/container.go',
    '/app/app/meta.go',
    '/app/theme/json.go',
    '/app/data/binding/sprintf.go',
    '/app/widget/toolbar.go',
    '/app/widget/hyperlink.go',
    '/app/widget/entry.go',
    '/app/data/validation/all.go',
    '/app/driver/desktop/app.go'
]

result = {
    'directories': {},
    'files': {}
}

for d in dirs_to_check:
    result['directories'][d] = os.path.isdir(d)

for f in files_to_check:
    result['files'][f] = os.path.isfile(f)

print(json.dumps(result, indent=2))


# Check if required files exist
import os

files_to_check = [
    '/app/app.go',           # Should have AppMetadata struct and App.Metadata() method
    '/app/app/app.go',       # Should have fyneApp.Metadata() implementation
    '/app/app/meta.go'       # Should have SetMetadata function
]

for f in files_to_check:
    exists = os.path.exists(f)
    print(f"{f}: {'EXISTS' if exists else 'MISSING'}")

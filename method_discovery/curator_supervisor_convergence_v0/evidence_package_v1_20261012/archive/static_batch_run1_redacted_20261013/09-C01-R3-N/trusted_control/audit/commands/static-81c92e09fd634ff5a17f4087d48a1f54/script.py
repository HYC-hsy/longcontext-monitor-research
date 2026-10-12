
import os

# Check if validation/all.go exists
validation_path = os.path.join("task", "workspace", "data", "validation")
if os.path.exists(validation_path):
    files = os.listdir(validation_path)
    print(f"Files in data/validation/: {files}")
    if 'all.go' in files:
        print("all.go EXISTS")
    else:
        print("all.go MISSING")
else:
    print("data/validation directory doesn't exist")

# Check if driver/desktop/app.go exists
desktop_path = os.path.join("task", "workspace", "driver", "desktop")
if os.path.exists(desktop_path):
    files = os.listdir(desktop_path)
    print(f"\nFiles in driver/desktop/: {files}")
    if 'app.go' in files:
        print("app.go EXISTS")
    else:
        print("app.go MISSING")
else:
    print("driver/desktop directory doesn't exist")

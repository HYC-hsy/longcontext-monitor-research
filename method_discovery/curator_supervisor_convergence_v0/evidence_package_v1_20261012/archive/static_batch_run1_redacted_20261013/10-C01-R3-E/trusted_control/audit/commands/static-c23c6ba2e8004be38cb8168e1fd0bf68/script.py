
# Search for Entry.SetMinRowsVisible method
import os

workspace = "task/workspace"
search_term = "SetMinRowsVisible"

# Try to find the method in entry.go
entry_file = os.path.join(workspace, "widget", "entry.go")

print(f"Checking if {search_term} exists in entry.go...")

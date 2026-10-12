
# Search through entry.go for SetMinRowsVisible method
print("=" * 80)
print("SEARCHING FOR SetMinRowsVisible IN entry.go")
print("=" * 80)

# Read entry.go in chunks using file_read
found_method = False
search_ranges = [(1, 500), (500, 1000), (1000, 1500), (1500, 1731)]

for start, end in search_ranges:
    print(f"\nChecking lines {start}-{end}...")

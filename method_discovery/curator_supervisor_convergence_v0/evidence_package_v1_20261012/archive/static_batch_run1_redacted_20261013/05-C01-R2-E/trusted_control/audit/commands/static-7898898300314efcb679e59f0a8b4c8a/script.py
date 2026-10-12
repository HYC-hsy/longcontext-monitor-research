
# Read the previous session output
with open(r"monitor/audit/commands/static-9ab2ba6cf8ec459a802b1869047606fb/output.log", 'r') as f:
    content = f.read()
print(content if content else "[Empty output]")


# Check git status to see if anything has been modified
cd /app && git status --short

# Check recent commits
cd /app && git log --oneline -10

# Check if there are any uncommitted changes
cd /app && git diff --name-only

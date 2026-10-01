[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;

# List workspace contents
Get-ChildItem -Path "E:\lc_seed_sessions_20261002\s03\workspace" -Recurse -File | Select-Object FullName, Length | Format-Table -AutoSize

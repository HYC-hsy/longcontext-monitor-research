[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;

# Check what files exist in the workspace
Get-ChildItem -Path "E:\runs\864be66e4a94c695f3ea0dbf\workspace" -Recurse -File | Select-Object FullName, Length | Format-Table -AutoSize

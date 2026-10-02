[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;

# List workspace structure to understand the codebase
Get-ChildItem -Path "E:\runs\5fd794fa34dac4121b7532dd\workspace" -Recurse -File | Select-Object FullName, Length

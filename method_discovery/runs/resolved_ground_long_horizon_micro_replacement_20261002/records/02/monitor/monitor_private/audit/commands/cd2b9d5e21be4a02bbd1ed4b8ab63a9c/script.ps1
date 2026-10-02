[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;

Get-ChildItem -Path "E:\runs\7db2cb1c1cfce4f0d5d7fc52\workspace" -Recurse -File | Select-Object FullName, Length | Format-Table -AutoSize

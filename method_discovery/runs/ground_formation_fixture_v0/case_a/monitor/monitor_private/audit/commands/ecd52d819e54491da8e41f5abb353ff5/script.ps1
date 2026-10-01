[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;

Get-ChildItem "E:\lc_seed_sessions_20261002\s01\workspace" -Recurse -File | Select-Object FullName, Length

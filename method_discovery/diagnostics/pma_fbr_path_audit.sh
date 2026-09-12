#!/bin/bash
# Read-only environment diagnosis; no task edits, network or model calls.
printf 'DIRECT_PATH=%s\n' "$PATH"
command -v go
/usr/local/go/bin/go version
printf '\nLOGIN_SHELL\n'
/bin/bash --login -c 'printf "LOGIN_PATH=%s\n" "$PATH"; command -v go; printf "GO_LOOKUP_EXIT=%s\n" "$?"; /usr/local/go/bin/go version'
printf '\nPROFILE_PATH_LINES\n'
grep -n 'PATH=' /etc/profile

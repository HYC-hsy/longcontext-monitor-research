#!/bin/sh
set -e
/opt/m4-runtime/python/cpython-3.12.12-linux-x86_64-gnu/bin/python3.12 -c "import urllib.request; assert urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:19173').status == 200"
mkdir -p /logs/verifier
printf "1\n" > /logs/verifier/reward.txt

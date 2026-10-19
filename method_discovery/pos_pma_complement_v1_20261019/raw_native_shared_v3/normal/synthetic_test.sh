#!/bin/sh
set -eu
test "$(cat /app/pos-fixture-marker.txt)" = POS_FILE_OK
/opt/m4-runtime/python/cpython-3.12.12-linux-x86_64-gnu/bin/python3.12 -c 'import urllib.request; response = urllib.request.build_opener(urllib.request.ProxyHandler({})).open("http://127.0.0.1:19173/", timeout=5); assert response.status == 200'
mkdir -p /logs/verifier
printf '1\n' > /logs/verifier/reward.txt

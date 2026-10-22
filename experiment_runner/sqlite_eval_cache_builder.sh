#!/usr/bin/env bash
# CONTAINER-ONLY online dependency builder. Invoked by evaluation_cache.py build.
# Host requires only its existing Python >=3.11 and Docker, not Bash/python3.
# No tests, scoring, model calls or Task image changes. Docker acceptance unrun
# in patch-authoring environment; host orchestrator marks readiness after success.
set -euo pipefail
: "${BASE_IMAGE:?must supply a trusted digest-pinned Task base image}"
[[ $BASE_IMAGE =~ ^[^[:space:]@]+@sha256:[0-9a-f]{64}$ ]] || exit 2
export HOME=/root
export UV_CACHE_DIR=/root/.cache/uv UV_PYTHON_INSTALL_DIR=/root/.local/share/uv/python
export UV_LINK_MODE=copy UV_NO_PROGRESS=1 UV_PYTHON_PREFERENCE=only-managed
# docker-clean has a Post-Invoke hook deleting cached .debs. Remove that builder-
# local hook BEFORE download-only; the resulting image is discarded, not committed.
rm -f /etc/apt/apt.conf.d/docker-clean
mkdir -p /var/cache/evaluation-debs/partial
apt-get -o Acquire::Retries=3 -o APT::Update::Error-Mode=any update
apt-get -o Acquire::Retries=3 -o Dir::Cache::archives=/var/cache/evaluation-debs \
  -o Binary::apt::APT::Keep-Downloaded-Packages=true --download-only --reinstall install -y curl
# Download-only retains curl plus the missing dependency closure for THIS base.
# Existing base libraries need not be duplicated, because the digest is pinned.
test -n "$(find /var/cache/evaluation-debs -maxdepth 1 -name "*.deb" -print -quit)"
dpkg -i /var/cache/evaluation-debs/*.deb
# Keep only .deb files, never APT locks or lists in the persistent bundle.
find /var/cache/evaluation-debs -mindepth 1 ! -name "*.deb" -delete
curl -fLsS --retry 3 https://astral.sh/uv/0.9.5/install.sh | sh
source /root/.local/bin/env
uv --version | grep -E "^uv 0[.]9[.]5([[:space:]]|$)"
uvx --version | grep -E "^uvx 0[.]9[.]5([[:space:]]|$)"
mkdir /dependency-check
cd /dependency-check
# Warm BOTH uvx tool keys used by the original bootstrap. Neither loads tests.
uvx -p 3.13 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 python -c "import importlib.metadata as m; print(m.version(\"pytest\")); print(m.version(\"pytest-json-ctrf\"))"
UV_OFFLINE=1 uvx -p 3.13 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 pytest --help | grep -F -- --ctrf
python_path=$(uv python find --offline 3.13)
export PYTHON_PATH="$python_path"
"$python_path" - <<'PY'
import json, os, platform, sys
sys.path.insert(0, "/builder")
from evaluation_cache import PROTOCOL, ORIGINAL_SHA256, VERSIONS, offline_check, publish_bundle
release = platform.freedesktop_os_release()
identity = dict(protocol=PROTOCOL, task="sqlite-with-gcov", original_sha256=ORIGINAL_SHA256,
    base_image=os.environ["BASE_IMAGE"], os_id=release["ID"], os_version=release["VERSION_ID"],
    architecture=platform.machine(), python=platform.python_version(),
    python_executable=os.path.realpath(os.environ["PYTHON_PATH"]), versions=VERSIONS)
offline_check(identity)
path = publish_bundle("/", "/output", identity)
print("BUNDLE=" + str(path))
# Identity is saved in each immutable manifest, not a mutable latest pointer.
PY

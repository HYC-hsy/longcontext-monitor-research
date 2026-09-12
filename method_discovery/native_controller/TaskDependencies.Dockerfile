# Build-only dependency preparation. Model execution remains network-less.
# Supply an audited task digest; never copy target-version source or tests.
ARG TASK_IMAGE
FROM ${TASK_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends asciinema \
    && rm -rf /var/lib/apt/lists/* \
    && tmux -V && asciinema --version
COPY preserve_image_path.py /tmp/preserve_image_path.py
RUN python3 /tmp/preserve_image_path.py && rm /tmp/preserve_image_path.py \
    && bash --login -c 'command -v go && go version'
# Intended only for Debian/Ubuntu tasks whose original user is root.
# Other distributions/users require explicit preparation, not silent fallback.

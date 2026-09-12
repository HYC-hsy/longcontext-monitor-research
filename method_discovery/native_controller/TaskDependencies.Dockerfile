# Build-only dependency preparation. Model execution remains network-less.
# Supply an audited task digest; never copy target-version source or tests.
ARG TASK_IMAGE
FROM ${TASK_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends asciinema \
    && rm -rf /var/lib/apt/lists/* \
    && tmux -V && asciinema --version
# Intended only for Debian/Ubuntu tasks whose original user is root.
# Other distributions/users require explicit preparation, not silent fallback.

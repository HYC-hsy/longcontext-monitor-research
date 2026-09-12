FROM docker:27-cli@sha256:851f91d241214e7c6db86513b270d58776379aacc5eb9c4a87e5b47115e3065c AS docker_cli
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
COPY --from=docker_cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker_cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 \
    LITELLM_LOCAL_MODEL_COST_MAP=True DOCKER_CONFIG=/tmp/docker
WORKDIR /workspace
COPY reference /workspace/some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent
RUN pip install --no-cache-dir \
    ./some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent/external/harbor \
    ./some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent \
    litellm==1.81.11 && pip check
COPY scripts /workspace/method_discovery
CMD ["python", "-m", "unittest", "discover", "-s", "method_discovery", "-p", "test_pma_native*.py", "-v"]

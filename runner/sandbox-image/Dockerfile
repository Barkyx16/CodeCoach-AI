# The image every untrusted submission runs in. It contains a JDK and one trusted entrypoint
# script, and nothing else is added. All isolation (gVisor, no network, read-only root,
# resource limits) is applied by the runner at `docker run` time; see runner/app/sandbox.py.
FROM eclipse-temurin:21-jdk-alpine

COPY --chmod=0555 run.sh /opt/judge/run.sh

# Unprivileged user. The runner also forces --user 65534:65534 at run time.
USER 65534:65534
WORKDIR /tmp
ENTRYPOINT ["/opt/judge/run.sh"]

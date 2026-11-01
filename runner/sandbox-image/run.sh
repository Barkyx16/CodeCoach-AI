#!/bin/sh
# Trusted entrypoint (baked into the image; learner code never sees it before it runs).
#
# stdin protocol:
#   line 1     per-run nonce (hex). Passed to the driver on ITS stdin, never via env/argv,
#              so learner code can't read it from /proc/self/environ or the command line.
#   remainder  base64-encoded tar containing exactly Solution.java and Main.java
#
# Exit codes: 90 bad input · 91 compile error (javac output on stderr) · otherwise java's code.
set -u
IFS= read -r NONCE || exit 90
mkdir -p /tmp/src /tmp/classes || exit 90
base64 -d | tar -x -C /tmp/src 2>/dev/null || exit 90
[ -f /tmp/src/Solution.java ] && [ -f /tmp/src/Main.java ] || exit 90

cd /tmp/src
if ! javac -J-Xmx256m -J-XX:+UseSerialGC -encoding UTF-8 -nowarn -d /tmp/classes Solution.java Main.java 2>/tmp/compile.err; then
  head -c 8192 /tmp/compile.err >&2
  exit 91
fi

echo "@@SANDBOX:RUN@@" >&2
printf '%s\n' "$NONCE" | java -Xmx"${HEAP_MB:-192}"m -Xss1m -XX:+UseSerialGC -XX:TieredStopAtLevel=1 \
  -XX:-UsePerfData -XX:+ExitOnOutOfMemoryError -cp /tmp/classes Main

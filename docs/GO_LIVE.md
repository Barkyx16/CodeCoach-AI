# Going live

From nothing to CodeCoach on your own domain over https, on one Linux server, in about 45
minutes. You run every step below yourself: it needs your accounts (a server and a domain), and
nothing in this repository buys, signs up for or publishes anything on its own.

What you get: the production compose (`deploy/docker-compose.production.yml`) with PostgreSQL,
the migrations, the API, the web app and, in front, **Caddy**, which gets and renews the https
certificate by itself. Optionally the **judge**, which runs visitors' Java in gVisor sandboxes.
`deploy/setup.sh` writes the settings with every secret generated on the server, and
`deploy/smoke-check.py` checks the result from outside, the way a visitor reaches it.

## 0. Three choices

| Choice | Pick | What it means |
|---|---|---|
| **Mode** | **demo** (recommended for a portfolio) | Visitors are guests: no sign-up, no email, no personal data kept. Two fictional sample learners, labelled. Guests are deleted a day after their last visit ([DEMO.md](DEMO.md)). |
| | full | Real accounts with email verification. Needs a mail provider (SMTP) and a sender domain with its SPF/DKIM records ([EMAIL.md](EMAIL.md)), and backups you schedule ([BACKUP.md](BACKUP.md)). |
| **Judge** | on | Submissions are compiled and run against the tests in gVisor sandboxes on the same server: the headline feature works for real. The runner uses the Docker socket (root on that server); it holds no other secret and no database access. The stricter layout puts it on a second server ([REMOTE_JUDGE.md](REMOTE_JUDGE.md)). |
| | off | Submissions are saved and say plainly that they weren't run. Everything else works. |
| **Server** | one Linux VM | Ubuntu 24.04 LTS, **x86-64**, a public IPv4 address. 2 vCPU and 4 GB RAM with the judge, 2 GB without; 25 GB disk. Any VPS provider with KVM virtual machines works (gVisor doesn't run in container-based "VPS"). Compare current prices; small VMs cost a few dollars a month. |

You also need a **domain or subdomain** you control (for example `codecoach.yourname.dev`). The
certificate is free (Let's Encrypt, through Caddy). The AI coach is the built-in one: nothing is
paid per use unless you choose Claude later.

## 1. The server and its address

1. Create the VM with Ubuntu 24.04 and your SSH key. Note its public IPv4 address.
2. At your DNS provider, add an **A record**: `codecoach.yourname.dev` → that address. (Add an
   AAAA record too if the server has IPv6.)
3. From your computer, wait until `dig +short codecoach.yourname.dev` prints the address.

## 2. Docker and the firewall

On the server (`ssh you@address`):

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl git
```

```bash
curl -fsSL https://get.docker.com | sudo sh
```

```bash
sudo usermod -aG docker "$USER"
```

Log out and back in (so `docker` works without `sudo`), then open only SSH and the web:

```bash
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 443/udp && sudo ufw --force enable
```

The compose file publishes only 80 and 443 to the world; the API and the app listen on
127.0.0.1, and the database and the runner on Docker's internal network only.

## 3. gVisor (only with the judge)

gVisor's own packages ([gvisor.dev/docs/user_guide/install](https://gvisor.dev/docs/user_guide/install/)):

```bash
curl -fsSL https://gvisor.dev/archive.key | sudo gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
```

```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main" | sudo tee /etc/apt/sources.list.d/gvisor.list > /dev/null
```

```bash
sudo apt-get update && sudo apt-get install -y runsc && sudo runsc install && sudo systemctl reload docker
```

Check that Docker now lists it and can start a sandbox:

```bash
docker info --format '{{json .Runtimes}}'
```

```bash
docker run --rm --runtime=runsc hello-world
```

## 4. The code and the settings

```bash
git clone https://github.com/Barkyx16/CodeCoach-AI.git && cd CodeCoach-AI
```

(If the repository is private, give the server a read-only **deploy key** in GitHub's repository
settings and clone over SSH.) Use the branch you want live: `main` once your pull request is
merged, or the working branch until then (`git checkout <branch>`).

Write the settings, with your domain:

```bash
deploy/setup.sh --domain codecoach.yourname.dev --judge
```

Leave out `--judge` if you skipped step 3; add `--mode full` for real accounts. It writes
`deploy/.env.production` and `deploy/.env.app`, readable by you only, with every password and key
generated there and never shown. It won't overwrite them: the database keeps the passwords it was
created with. With `--mode full`, now fill in `SMTP_*` and `EMAIL_FROM` in `deploy/.env.app` from
your mail provider.

## 5. Start it

```bash
docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml up -d --build
```

The first build takes a few minutes. Then, for the demo, load the sample learners (the command
asks for the database's name as confirmation):

```bash
docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml run --rm migrate python -m app.cli demo-reset --confirm codecoach_demo
```

Caddy asks Let's Encrypt for the certificate as soon as it starts; with the DNS record in place it
arrives within a minute. Watch it with `docker compose … logs -f proxy`.

## 6. Check it

The preflight, inside the API container: nothing may be **blocked**.

```bash
docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml exec api python -m app.cli preflight
```

With the judge, prove a real submission runs in the sandbox:

```bash
docker compose --env-file deploy/.env.production -f deploy/docker-compose.production.yml exec worker python -m app.cli judge-check
```

Then from your own computer, the way a visitor reaches it (Python 3.9+, nothing to install):

```bash
python3 deploy/smoke-check.py https://codecoach.yourname.dev
```

It checks the certificate, the security headers, readiness, the session cookie, a graded
answer, a judged submission (with the judge on), that a second visitor can't see the first one's
work, and, on the demo, that accounts are refused. Last, open the site in a private window and
take the ten-minute walkthrough in [DEMO.md](DEMO.md), on a phone too.

## 7. Keeping it running

- **Updates:** `git pull`, then the same `up -d --build`. The migrate job brings the database up to
  date before the new API starts; data stays. Never `down -v`: it deletes the database volume.
- **Reboots:** every service restarts by itself (`restart: unless-stopped`).
- **Is it up?** Point a free uptime monitor at `https://codecoach.yourname.dev/health/ready`
  (200 when the API and the database are fine; 503 otherwise) and have it email you.
- **Logs:** `docker compose … logs -f api` (or `proxy`, `worker`, `runner`, `db`).
- **The demo's starting state:** visitors' guests delete themselves after a day. To put the sample
  learners back exactly as they were, run the `demo-reset` command again.
- **Backups:** the demo can always be recreated with `demo-reset`. With real accounts, schedule the
  nightly backup and copy it off the server ([BACKUP.md](BACKUP.md), "Scheduling").
- **Disk:** after several updates, `docker image prune` removes old images.
- **Claude instead of the built-in coach:** set `AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` in
  `deploy/.env.app`, keep `AI_APP_DAILY_PAID_CALL_LIMIT` low, set a spending limit in the
  provider's console too, and `up -d` again ([SECURITY.md](SECURITY.md), "AI spending").

## When something's wrong

| Symptom | Look at | Usually |
|---|---|---|
| The browser says the certificate is invalid, or nothing answers | `docker compose … logs proxy` | The DNS record doesn't point at this server yet, or ports 80/443 are closed (step 1, step 2). Let's Encrypt also limits repeated failed attempts: fix the cause, then wait an hour. |
| 502 right after starting | `docker compose … ps` | The API is still starting (it waits for the migrations); healthy within a minute. |
| The API keeps restarting | `docker compose … logs api` | A setting the production checks refuse; the message names it. With `--mode full`: the SMTP settings. |
| Submissions say "unavailable" | `docker compose … logs runner`, then `judge-check` | gVisor isn't installed or registered (step 3), or the runner is still starting. |
| Anything else | [LAUNCH.md](LAUNCH.md), "When something breaks" | |

## What was rehearsed, and what wasn't

Rehearsed on 2026-11-25 in a Linux sandbox (Docker 29.9.2, gVisor `runsc` registered), with
`deploy/setup.sh --domain localhost --judge` and the compose above. Caddy served `https://localhost`
from its own local certificate authority instead of Let's Encrypt; the sandbox's network needs a
certificate added to the image builds, so the images were built from copies of the Dockerfiles
with that one change (CI builds the real ones).

- The stack started: database, migrations, API, web, proxy, runner, worker. The preflight: 10 ready,
  0 blocked, 2 optional (mail in demo mode, the built-in coach), 2 unverified (backups, and code
  execution, which `judge-check` then passed: a correct solution passed 3/3 in the sandbox and a
  wrong one was rejected).
- `deploy/smoke-check.py https://localhost` with the certificate verified: every check passed,
  among them a submission judged PASSED in the gVisor sandbox in 4.1 s, a nurse's answer graded,
  the session cookie `__Host-`, Secure, HttpOnly and SameSite=Strict, a second visitor refused the
  first one's submission (404), and registration refused in demo mode (403).
- `down` and `up` again: the data and the certificate authority were kept, and the checks passed
  again. The logs had no errors.
- The rehearsal found one defect, fixed before this was committed: the migrate job read the
  judge's switch from the shared settings without the judge's token and refused to start. Jobs
  that run no learner code now keep the judge off (`tests/test_go_live.py`).

Not shown here: Let's Encrypt issuing a certificate for a real domain, gVisor on your provider's
VM, and traffic from the internet. Steps 1 to 6 on the real server show those, and
`smoke-check.py` is the check that matters there.

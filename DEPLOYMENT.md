# Deployment Guide — Pratyin HRMS

Reference steps for deploying this stack (Frappe + ERPNext fork + HRMS + India Payroll fork) to a
production server. Written for the setup actually used for this project: a fresh Ubuntu/Debian VPS,
deployed with Docker via [frappe_docker](https://github.com/frappe/frappe_docker), starting on
plain IP access (no domain/SSL yet — see [Adding a domain later](#adding-a-domain--https-later)).

If you're setting up a **local development** bench instead, see the main [README.md](README.md) —
this file is production deployment only.

### Repos used

| App | Source | Branch |
|---|---|---|
| `frappe` | `https://github.com/frappe/frappe` (official, unforked) | `version-16` |
| `erpnext` | `https://github.com/PratyinInfotech/pratyin-erpnext` (our fork — carries the merged Home sidebar) | `version-16` |
| `hrms` | `https://github.com/frappe/hrms` (official, unforked) | `version-16` |
| `india_payroll` | `https://github.com/PratyinInfotech/pratyin-india-payroll` (our fork — carries the theme/branding/sidebar customizations) | `version-16` |

`frappe` and `hrms` are unmodified, so they're pulled straight from Frappe's own repos — only the
two forks above need to be built in.

---

## 1. Prep the server

```bash
ssh youruser@your-server-ip

sudo apt update && sudo apt upgrade -y

# Install Docker Engine + Compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker   # or log out/in for the group change to apply

docker --version
docker compose version
```

## 2. Build the custom image

```bash
git clone https://github.com/frappe/frappe_docker
cd frappe_docker
```

Create `apps.json` — lists every app on top of Frappe itself (Frappe is passed as a separate build
arg, not listed here):

```bash
cat > apps.json << 'EOF'
[
  { "url": "https://github.com/PratyinInfotech/pratyin-erpnext", "branch": "version-16" },
  { "url": "https://github.com/frappe/hrms", "branch": "version-16" },
  { "url": "https://github.com/PratyinInfotech/pratyin-india-payroll", "branch": "version-16" }
]
EOF

export APPS_JSON_BASE64=$(base64 -w 0 apps.json)

docker build \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH=version-16 \
  --build-arg=APPS_JSON_BASE64=$APPS_JSON_BASE64 \
  --tag=pratyin-hrms:latest \
  --file=images/layered/Containerfile .
```

Expect 15–30+ minutes on a modest VPS — it's compiling assets for all four apps.

> **Note:** frappe_docker's exact compose file names and env vars have shifted between releases.
> Before step 3, check `cat frappe_docker/README.md` on the server to confirm the current file names
> still match what's below — this guide follows the stable, documented pattern, not a pinned version.

## 3. Deploy with Docker Compose (IP-only, no domain)

```bash
cp example.env .env
```

Edit `.env` — set at minimum:

```
DB_PASSWORD=<a strong password>
DB_HOST=db
DB_PORT=3306
REDIS_CACHE=redis-cache:6379
REDIS_QUEUE=redis-queue:6379
FRAPPE_SITE_NAME_HEADER=<your-server-ip>
```

Point the compose file(s) at the custom image built in step 2 (either export `CUSTOM_IMAGE=pratyin-hrms`
/ `CUSTOM_TAG=latest`, or edit the `image:` lines directly), then:

```bash
docker compose -f compose.yaml -f overrides/compose.mariadb.yaml -f overrides/compose.redis.yaml up -d
```

## 4. Create the site

```bash
docker compose exec backend bench new-site your-server-ip \
  --mariadb-root-password <db-root-password> \
  --admin-password <admin-password> \
  --no-mariadb-socket

docker compose exec backend bench --site your-server-ip install-app erpnext
docker compose exec backend bench --site your-server-ip install-app hrms
docker compose exec backend bench --site your-server-ip install-app india_payroll

docker compose exec backend bench --site your-server-ip set-config developer_mode 0
docker compose exec backend bench --site your-server-ip enable-scheduler
```

**Mandatory — force-sync the merged Home sidebar.** The automatic fixture sync that runs as
part of `install-app erpnext` can end up incomplete on a fresh site (large insert, modest VPS
resources) with no visible error, leaving the sidebar empty or partial. Don't rely on it —
always force a full reset from the shipped `home.json` right after the three `install-app` calls
above:

```bash
docker compose exec backend bench --site your-server-ip execute \
  india_payroll.india_payroll.scripts.customize_sidebar.restore_modules
```

Then verify it actually landed before moving on:

```bash
docker compose exec backend bench --site your-server-ip console
>>> frappe.db.count("Workspace Sidebar Item", {"parent": "Home"})
```

This should print `645`. If it's 0 or noticeably lower even after `restore_modules`, the install
itself failed partway — check `docker compose logs backend` around the `install-app erpnext`
timestamp for a traceback (often a MariaDB `max_allowed_packet` or memory limit on small VPS
instances) before continuing.

**Mandatory — land on `/desk/home` after login, not bare `/desk`.** The desk login form logs in via
an AJAX call and navigates to whatever `home_page` the login response carries
(`apps/frappe/frappe/templates/includes/login/login.js`). For a System User that value comes from
`frappe.website.utils.get_home_page()`, not from `default_app`/`get_default_path()` (that pair only
governs Website User logins). `get_home_page()` falls back to the bare `"desk"` route unless
something resolves it first, in this priority order:
1. `User.default_workspace` on that specific user (wins over everything below, if set)
2. the `role_home_page` hook, keyed by role

`india_payroll` sets `role_home_page = {"All": "desk/home"}` (`"All"` is a role every user has), so
this applies automatically on install — no extra command needed here, unlike the sidebar fix above.
It only silently loses if some user's `default_workspace` is already set to something else, which
takes priority — check with:

```bash
docker compose exec backend bench --site your-server-ip execute frappe.db.get_value --args "['User', 'Administrator', 'default_workspace']"
```
If that prints anything other than empty/`Home`, either clear it or set it to `Home` explicitly:
```bash
docker compose exec backend bench --site your-server-ip execute frappe.db.set_value --args "['User', 'Administrator', 'default_workspace', 'Home']"
```

Either way, finish with a cache clear — `get_home_page()` results are cached per-user in Redis and
won't reflect a hooks.py change (or a `default_workspace` edit) until cleared:
```bash
docker compose exec backend bench --site your-server-ip clear-cache
```

## 5. Open the firewall and access it

```bash
sudo ufw allow 8080/tcp   # or whatever port the frontend container publishes — check `docker compose ps`
```

Visit `http://your-server-ip:8080`.

---

## Adding a domain + HTTPS later

Swap in frappe_docker's Traefik-based compose overrides for automatic Let's Encrypt HTTPS once DNS
is pointed at the server — that's a compose config change, not a rebuild, so steps 1–4 don't need
to be redone.

## Updating a deployed instance

When new commits land on either fork (`pratyin-erpnext` or `pratyin-india-payroll`):

```bash
cd frappe_docker
# re-run the docker build from step 2 (same command, same tag or a new one)
docker compose up -d   # recreates containers on the new image
docker compose exec backend bench --site your-server-ip migrate
```

If the update touched sidebar content (`home.json` or any file under `workspace_sidebar/`), follow
with the same force-sync used on a fresh install — `bench migrate` intentionally won't overwrite a
Workspace Sidebar it considers already customized once the DB row exists, so new sidebar items
never reach a live site through `migrate` alone:

```bash
docker compose exec backend bench --site your-server-ip execute \
  india_payroll.india_payroll.scripts.customize_sidebar.restore_modules
```

## Backups

```bash
docker compose exec backend bench --site your-server-ip backup --with-files
```

Schedule this via cron on the host, and copy the resulting backup files off the server periodically
(the site's `private/backups` folder inside the container volume).

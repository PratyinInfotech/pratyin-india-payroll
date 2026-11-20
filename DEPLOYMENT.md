# Deployment Guide — Pratyin HRMS

Reference steps for deploying this stack (Frappe + ERPNext fork + HRMS + India Payroll fork) to a
production server. Written for the setup actually used for this project: a fresh Ubuntu/Debian VPS,
deployed with Docker via [frappe_docker](https://github.com/frappe/frappe_docker), starting on
plain IP access (no domain/SSL yet — see [Adding a domain later](#adding-a-domain--https-later)).

If you're setting up a **local development** bench instead, see the main [README.md](README.md) —
this file is production deployment only.

### Repos used

| App | Source | Ref | Commit |
|---|---|---|---|
| `frappe` | `https://github.com/frappe/frappe` (official, unforked) | tag `v16.31.0` | `6a329d0684` |
| `erpnext` | `https://github.com/PratyinInfotech/pratyin-erpnext` (our fork — carries the merged Home sidebar) | `version-16` | `8eee0bd3b9` |
| `hrms` | `https://github.com/frappe/hrms` (official, unforked) | tag `v16.16.0` | `f281e8b172` |
| `india_payroll` | `https://github.com/PratyinInfotech/pratyin-india-payroll` (our fork — carries the theme/branding/sidebar customizations) | `version-16-add-loginpage` | `1bbb136` |

**Pin to tags, never to `version-16`, for the two official repos.** `version-16` is a moving
development branch — Frappe pushes to it continuously. Building against it means every rebuild
silently picks up whatever landed upstream that day, so the server drifts away from the local bench
with no change on our side. This has already bitten this project once: a server built from
`version-16` ran roughly three months of newer frappe/hrms than local, which is why the deployed
desk UI did not match.

The two tags above point at byte-identical commits to the local dev bench (verified by comparing
full SHAs — a matching commit SHA is git's proof that the file trees are identical). `git clone
--branch` accepts tags, so no fork of `frappe` or `hrms` is needed.

**`india_payroll` builds from `version-16-add-loginpage`, not `version-16`.** The fork's
`version-16` branch is months behind and lacks both the login page redesign and the
`refuse_new_rows` fix in `customize_sidebar.py`. Building from it produces a server that throws
`Home is an archive and can no longer be edited` during the sidebar step below. Once that work is
merged back into `version-16`, update this table and `apps.json` together.

When upgrading, move local and the server to the same new tag in the same change — never let one
side float.

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
  { "url": "https://github.com/frappe/hrms", "branch": "v16.16.0" },
  { "url": "https://github.com/PratyinInfotech/pratyin-india-payroll", "branch": "version-16-add-loginpage" }
]
EOF

export APPS_JSON_BASE64=$(base64 -w 0 apps.json)

docker build \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH=v16.31.0 \
  --build-arg=APPS_JSON_BASE64=$APPS_JSON_BASE64 \
  --tag=pratyin-hrms:latest \
  --file=images/layered/Containerfile .
```

Expect 15–30+ minutes on a modest VPS — it's compiling assets for all four apps.

### Verify the build got the right code

Do this before creating the site — it's the cheapest possible check and it catches a wrong pin
before any site data exists. After the stack is up (step 3), run:

```bash
docker compose exec backend bash -c 'for a in frappe erpnext hrms india_payroll; do printf "%-16s " "$a"; git -C apps/$a rev-parse HEAD; done'
```

Expected output — these must match exactly:

```
frappe           6a329d068416768ec47ccd3326b9cc95a8d7bf99
erpnext          8eee0bd3b9b76709f2e85947594beb006d46dfa8
hrms             f281e8b172ac8836ad89c59df65a922101103097
india_payroll    1bbb13682f88fc7a3d2c144c2fbfbdaf7ef86a22
```

Any mismatch means `apps.json` or `FRAPPE_BRANCH` was wrong — fix it and rebuild rather than
continuing, since every UI difference chased later traces back to this.

If the image was built without the `.git` directories and `rev-parse` fails, fall back to version
numbers — less precise, but enough to catch a wrong pin:

```bash
docker compose exec backend bench version
```

`frappe` must report `16.31.0` and `hrms` `16.16.0`.

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

**Mandatory — import the Home sidebar record first.** On a fresh site the `Workspace Sidebar`
record named `Home` often does not get created at all by `install-app erpnext`, even though
`frappe.model.sync` is supposed to pick up `workspace_sidebar/*.json`. Without it the next step
fails with `Workspace Sidebar Home not found`, and the desk falls back to whatever sidebar it can
find (usually `hr-setup` or `setup`), which looks like a theme or routing bug but is not.

Force-import it directly:

```bash
docker compose exec backend bench --site your-server-ip execute \
  frappe.modules.import_file.import_file_by_path \
  --args "['/home/frappe/frappe-bench/apps/erpnext/erpnext/workspace_sidebar/home.json', True]"
```

This prints `true` when it imported. The `True` is `force=True`, which bypasses the
timestamp/hash checks that otherwise cause `import_file_by_path` to skip the file.

**Then force-sync the sidebar contents.** The automatic fixture sync can also end up incomplete on
a fresh site (large insert, modest VPS resources) with no visible error, leaving the sidebar empty
or partial. Don't rely on it — always force a full reset from the shipped `home.json`:

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

**Then trim the sidebar to the HRMS-only module set:**

```bash
docker compose exec backend bench --site your-server-ip execute \
  india_payroll.india_payroll.scripts.customize_sidebar.hide_modules
```

Expect `Removed 13 module section(s): Banking, Budget, ERPNext Settings, ...`. A trailing
`Not found (already removed, or label mismatch?): CRM, Support` line is normal — those labels
differ between ERPNext versions and nothing depends on them being hidden.

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
takes priority.

Check **every** System User, not just Administrator — the person actually logging in to a demo or
production site is usually a named user created by the setup wizard, and setting it on
Administrator alone does nothing for them:

```bash
docker compose exec backend bench --site your-server-ip execute frappe.client.get_list \
  --kwargs "{'doctype':'User','filters':{'user_type':'System User'},'fields':['name','default_workspace'],'limit_page_length':50}"
```

For any user showing `null` (or anything other than `Home`), set it explicitly:

```bash
docker compose exec backend bench --site your-server-ip execute frappe.db.set_value \
  --args "['User', 'their.email@example.com', 'default_workspace', 'Home']"
```

Note that `default_workspace` is resolved against the **`Workspace`** doctype, not `Workspace
Sidebar` (`frappe/utils/user.py`, `load_user()`), and a missing target is swallowed silently —
`d.default_workspace` is just set to `None`, with no error anywhere. So if landing still goes to
the wrong place, confirm the `Workspace` record exists before suspecting anything else:

```bash
docker compose exec backend bench --site your-server-ip execute frappe.client.get_list \
  --kwargs "{'doctype':'Workspace','filters':{'name':'Home'},'fields':['name','module','public'],'limit_page_length':5}"
```

Its `module` is `Setup`, so the resulting desk URL is `/desk/setup/home` — that is the Home
workspace loading correctly, **not** a redirect into the setup wizard. Don't chase it as a bug.

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

docker compose exec backend bench --site your-server-ip execute \
  india_payroll.india_payroll.scripts.customize_sidebar.hide_modules

docker compose exec backend bench --site your-server-ip clear-cache
```

`restore_modules` resets to the full 645-item list, so `hide_modules` must always run after it —
otherwise the hidden ERPNext modules reappear.

### Upgrading frappe or hrms

Never bump these on the server alone. Upgrade the local bench to the new tag first, confirm the UI
still behaves, then update the **Repos used** table, `apps.json`, and `FRAPPE_BRANCH` to the same
tag in one change, and rebuild. The whole point of pinning is that local and the server move
together — bumping one side reintroduces exactly the drift this setup exists to prevent.

## Backups

```bash
docker compose exec backend bench --site your-server-ip backup --with-files
```

Schedule this via cron on the host, and copy the resulting backup files off the server periodically
(the site's `private/backups` folder inside the container volume).

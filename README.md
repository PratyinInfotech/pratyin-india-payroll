### India Payroll (Custom HR Fork)

A Frappe HR extension app to simplify payroll and taxes according to Indian rules and regulations — this fork additionally carries a custom Desk experience for this deployment: no `/desk` app-picker landing, a single unified module sidebar, a 4th "Custom" desk theme, and several sidebar UX fixes.

---

### What this fork changes vs. upstream

| Area | Change | Where |
|---|---|---|
| Landing page | Skips the v16 `/desk` app-picker grid; lands directly on the merged module sidebar | `india_payroll/page/home_redirect/`, System Default `desktop:home_page` |
| Sidebar | All modules merged into one "Home" `Workspace Sidebar` with dropdown sections, instead of one workspace at a time | ERPNext fork — see [Related repositories](#related-repositories) |
| Theme | New 4th "Custom" option in the stock Switch Theme dialog (alongside Light / Dark / Automatic), Bootstrap-blue palette, colored topbar, card shadows, styled table/list headers | `public/css/custom_theme.css`, `public/js/custom_theme_switcher.js` |
| Sidebar fixes | Collapsed-sidebar icon clipping, inconsistent Desktop-dropdown redirect, sections re-expanding on refresh, stray onboarding popup, orphaned shortcut links regrouped under Shortcuts | `public/js/custom_theme_switcher.js`, `hooks.py` |

None of this touches Frappe core or HRMS — it's additive via `app_include_css` / `app_include_js` hooks and one custom `Page` doctype, so upstream `india_payroll` updates can still be pulled and merged normally.

### Related repositories

This deployment also carries one customization inside ERPNext itself (the merged `Home` Workspace Sidebar at `erpnext/workspace_sidebar/home.json`) that couldn't live in this app, since it edits ERPNext's own fixture data. That lives in a matching fork:

| App | Repo | Branch | Notes |
|---|---|---|---|
| `frappe` | https://github.com/frappe/frappe (stock, unforked) | `version-16` | |
| `erpnext` | `<your-github-username>/erpnext` (fork) | `version-16` | carries `erpnext/workspace_sidebar/home.json` |
| `hrms` | https://github.com/frappe/hrms (stock, unforked) | `version-16` | |
| `india_payroll` | `<your-github-username>/india_payroll` (this repo) | `version-16` | |

Replace `<your-github-username>` below with wherever you push these two forks.

---

### Prerequisites

Tested with these versions on this deployment — close minor versions should work, but treat this table as the known-good baseline:

- Python 3.12 (⚠️ this app's `pyproject.toml` currently declares `requires-python = ">=3.14"` — that appears to be unintentional template boilerplate, since the app runs fine on 3.12.3 here; fix it in `pyproject.toml` before it trips up a stricter installer, or confirm 3.14 is genuinely intended)
- Node.js 24.x, Yarn 1.22.x
- MariaDB 10.11+ (or Postgres, if you'd rather run Frappe on that)
- Redis 7.x (cache, queue, and socketio — bench runs three separate instances)
- `wkhtmltopdf` (for PDF print formats — not currently installed on this box; install it before relying on PDF generation)
- [bench CLI](https://github.com/frappe/bench) 5.x

### New developer setup

```bash
# 1. Install bench (skip if already installed)
pip install frappe-bench

# 2. Create a new bench (pulls Frappe core, stock)
bench init hr-bench --frappe-branch version-16
cd hr-bench

# 3. Get the stock apps
bench get-app hrms --branch version-16
# (erpnext is pulled automatically as an hrms dependency — if not, add it explicitly:)
# bench get-app erpnext --branch version-16

# 4. Get the two customized forks instead of stock erpnext/india_payroll
bench get-app erpnext https://github.com/<your-github-username>/erpnext.git --branch version-16 --overwrite
bench get-app india_payroll https://github.com/<your-github-username>/india_payroll.git --branch version-16

# 5. Create the site
bench new-site hr.local --db-type mariadb
# (follow the prompts for the MariaDB root password and a new Administrator password)

# 6. Install the apps, in dependency order
bench --site hr.local install-app erpnext
bench --site hr.local install-app hrms
bench --site hr.local install-app india_payroll

# 7. Point the site at /desk skip + the merged sidebar (one-time, done automatically by
#    india_payroll's after_install hook — verify it landed):
bench --site hr.local console
>>> import frappe
>>> frappe.db.get_default("desktop:home_page")   # should print "home-redirect"
>>> exit()

# 8. Run it
bench start
```

Then visit `http://hr.local:8000` (add `127.0.0.1 hr.local` to `/etc/hosts` first if running locally).

Log in as Administrator — you should land directly on the merged module sidebar, no `/desk` app-picker grid. Open the profile menu → **Switch Theme** to see the 4th "Custom" theme.

---

### Production deployment

This covers a single-server deployment with `bench`'s built-in production setup (supervisor + nginx). For containerized/multi-server deployment, see the [Frappe Docker](https://github.com/frappe/frappe_docker) alternative at the end.

```bash
# 1. On the production server, repeat the "New developer setup" steps above through
#    step 6 (get-app + new-site + install-app), using a production-appropriate site
#    name (e.g. hr.yourcompany.com) and a strong Administrator/DB password.

# 2. Set the site as default and turn off maintenance/developer mode
bench use hr.yourcompany.com
bench --site hr.yourcompany.com set-config developer_mode 0
bench --site hr.yourcompany.com set-config maintenance_mode 0

# 3. Generate supervisor + nginx configs and wire them up (run as a sudo-capable user)
sudo bench setup production $(whoami)

# 4. Enable HTTPS (Let's Encrypt) — requires the domain's DNS already pointed at this server
sudo bench setup lets-encrypt hr.yourcompany.com

# 5. Restart everything cleanly after any deploy
sudo supervisorctl restart all
sudo bench restart   # if using the systemd path instead of supervisor
```

**Deploying updates later:**

```bash
cd hr-bench
bench --site hr.yourcompany.com set-maintenance-mode on
bench update --pull --apps india_payroll erpnext frappe hrms   # or `bench update` for everything
bench --site hr.yourcompany.com migrate
bench --site hr.yourcompany.com set-maintenance-mode off
sudo supervisorctl restart all
```

**Backups** (schedule this via cron):

```bash
bench --site hr.yourcompany.com backup --with-files
```

**Alternative: Frappe Docker**

If you'd rather run this as containers, use [frappe_docker](https://github.com/frappe/frappe_docker)'s custom-image build with an `apps.json` pointing at the two forks:

```json
[
  { "url": "https://github.com/frappe/frappe", "branch": "version-16" },
  { "url": "https://github.com/<your-github-username>/erpnext.git", "branch": "version-16" },
  { "url": "https://github.com/frappe/hrms", "branch": "version-16" },
  { "url": "https://github.com/<your-github-username>/india_payroll.git", "branch": "version-16" }
]
```

Follow frappe_docker's "Build Your Own Images" guide, base64-encode this `apps.json` into `APPS_JSON_BASE64`, and build.

---

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/india_payroll
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.

### License

gpl-3.0

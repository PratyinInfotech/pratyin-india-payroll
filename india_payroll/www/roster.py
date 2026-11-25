"""Serve Frappe HR's roster planner (``/hr/...``) under Pratyin branding.

hrms routes ``/hr/<path:app_path>`` to its ``roster`` www page (see
``hrms/hooks.py``), which is a *second*, separate Vue bundle from the one
behind ``/hrms``. Branding the mobile portal therefore left this page stock,
which is why the roster still introduced itself as "Frappe HR".

This shadows ``hrms/www/roster.html`` the same way ``www/hrms.py`` shadows the
portal: Frappe's TemplatePage walks ``reversed(frappe.get_installed_apps())``
looking for ``www/<page>``, and india_payroll installs after hrms, so this copy
is found first. Shadowing — rather than editing hrms in place — keeps the
branding intact across ``bench update`` and keeps every Pratyin change inside
this repo.

The one thing that must NOT be copied is the compiled asset list. Vite
re-hashes ``index-*.js`` / ``index-*.css`` on every ``bench build``, so a
hard-coded tag set would serve a 404 bundle and white-screen the planner the
first time anyone rebuilt hrms. Those tags are lifted out of hrms's own
template at render time instead, which means this page follows hrms's build
automatically.
"""

import os
import re

import frappe

no_cache = 1

BRAND_NAME = "Pratyin HR"

# Matches the <script src> / <link href> tags vite injects for the compiled
# bundle. Anchored on the /assets/hrms/roster/ prefix so nothing else in the
# document is picked up.
ASSET_TAG_PATTERN = re.compile(
	r"""<script\b[^>]*\bsrc=["']/assets/hrms/roster/[^"']+["'][^>]*>\s*</script>"""
	r"""|<link\b[^>]*\bhref=["']/assets/hrms/roster/[^"']+["'][^>]*>""",
	re.IGNORECASE,
)

# hrms's template also carries <link rel="icon">. Ours replaces it with the
# Pratyin favicon, so that tag is dropped on the way through.
ICON_TAG_PATTERN = re.compile(r"""\brel=["']icon["']""", re.IGNORECASE)


def get_context(context):
	# Mirrors hrms/www/roster.py.
	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # nosemgrep

	context = frappe._dict()
	context.csrf_token = csrf_token
	context.brand_name = BRAND_NAME
	context.roster_asset_tags = get_roster_asset_tags()
	return context


def get_roster_asset_tags() -> str:
	"""Return hrms's compiled roster <script>/<link> tags, in document order."""
	template_path = os.path.join(frappe.get_app_path("hrms"), "www", "roster.html")

	try:
		# frappe-security-file-traversal fires on any open() call -- the rule is a
		# bare `pattern: open(...)` with no taint analysis. template_path is built
		# entirely from constants (get_app_path plus two literals) and never from
		# request data, so there is no traversal to audit.
		with open(template_path, encoding="utf-8") as template:  # nosemgrep
			source = template.read()
	except OSError as exc:
		frappe.throw(
			frappe._(
				"Could not read {0}. Frappe HR's roster frontend has not been built — "
				"run `bench build --app hrms`."
			).format(template_path),
			exc=exc,
		)

	tags = [
		match.group(0)
		for match in ASSET_TAG_PATTERN.finditer(source)
		if not ICON_TAG_PATTERN.search(match.group(0))
	]

	if not tags:
		frappe.throw(
			frappe._("No compiled roster assets found in {0}. Run `bench build --app hrms`.").format(
				template_path
			)
		)

	return "\n\t\t".join(tags)

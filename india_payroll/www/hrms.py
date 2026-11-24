"""Serve the Frappe HR mobile portal (``/hrms``) under Pratyin branding.

This shadows ``hrms/www/hrms.html``: Frappe's TemplatePage walks
``reversed(frappe.get_installed_apps())`` looking for ``www/<page>``, and
india_payroll installs after hrms, so this copy is found first. Shadowing —
rather than editing hrms in place — keeps the branding intact across
``bench update`` and keeps every Pratyin change inside this repo.

The one thing that must NOT be copied is the compiled asset list. Vite
re-hashes ``index-*.js`` / ``index-*.css`` on every ``bench build``, so a
hard-coded tag set would serve a 404 bundle and white-screen the portal the
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
# bundle. Anchored on the /assets/hrms/frontend/ prefix so nothing else in the
# document is picked up.
ASSET_TAG_PATTERN = re.compile(
	r"""<script\b[^>]*\bsrc=["']/assets/hrms/frontend/[^"']+["'][^>]*>\s*</script>"""
	r"""|<link\b[^>]*\bhref=["']/assets/hrms/frontend/[^"']+["'][^>]*>""",
	re.IGNORECASE,
)

# vite also injects its own <link rel="manifest">. Ours replaces it, so that
# tag is dropped on the way through.
MANIFEST_TAG_PATTERN = re.compile(r"""\brel=["']manifest["']""", re.IGNORECASE)


def get_context(context):
	# Mirrors hrms/www/hrms.py: the boot payload the Vue app reads on startup
	# is imported rather than reimplemented so it tracks hrms's own changes.
	from hrms.www.hrms import get_boot

	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # nosemgrep

	context = frappe._dict()
	context.csrf_token = csrf_token
	context.boot = get_boot()
	context.site_name = frappe.local.site
	context.brand_name = BRAND_NAME
	context.hrms_asset_tags = get_hrms_asset_tags()
	return context


def get_hrms_asset_tags() -> str:
	"""Return hrms's compiled <script>/<link> tags, in document order."""
	template_path = os.path.join(frappe.get_app_path("hrms"), "www", "hrms.html")

	try:
		with open(template_path, encoding="utf-8") as template:
			source = template.read()
	except OSError as exc:
		frappe.throw(
			frappe._(
				"Could not read {0}. Frappe HR's frontend has not been built — "
				"run `bench build --app hrms`."
			).format(template_path),
			exc=exc,
		)

	tags = [
		match.group(0)
		for match in ASSET_TAG_PATTERN.finditer(source)
		if not MANIFEST_TAG_PATTERN.search(match.group(0))
	]

	if not tags:
		frappe.throw(
			frappe._(
				"No compiled frontend assets found in {0}. Run `bench build --app hrms`."
			).format(template_path)
		)

	return "\n\t\t".join(tags)

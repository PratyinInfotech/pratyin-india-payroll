import json
import os

import frappe
from frappe.modules.utils import create_directory_on_app_path

# IMPORTANT — developer_mode caveat, verified by testing on a dev bench:
# WorkspaceSidebar.export_sidebar() re-writes this app's own home.json file
# on every doc.save() whenever site_config developer_mode is 1, which is
# exactly what hide_modules()/restore_modules() do internally. On a
# production site (developer_mode 0, the normal state) this never happens —
# both functions only ever touch the database, and the installed home.json
# stays pristine as the permanent source of truth for restore_modules().
# On a DEV bench with developer_mode on, though, running hide_modules() will
# also strip the file itself, so a later restore_modules() has nothing left
# to recover from — first `git checkout -- .../workspace_sidebar/home.json`
# to get the file back before restoring, same as any other file edit.

# Modules verified (by grepping every Link field in hrms + india_payroll) to
# have zero code dependency from HR/Payroll functionality — safe to hide
# outright for a pure HRMS deployment (e.g. a bank or IT services company
# with no use for Stock/Manufacturing/Selling/CRM/etc.). Assets, Projects,
# and Buying are deliberately left out of this default list since they're
# used by optional HR features (asset return tracking, project-linked
# expenses, training vendor selection) — pass them explicitly if unwanted.
DEFAULT_MODULES_TO_HIDE = [
	"Stock",
	"Manufacturing",
	"Selling",
	"CRM",
	"Quality",
	"Subscription",
	"Support",
	"Invoicing",
	"Banking",
	"Taxes",
	"Financial Reports",
	"Share Management",
	"Budget",
	"Subcontracting",
	"ERPNext Settings",
]


def hide_modules(modules: list[str] | None = None, sidebar: str = "Home"):
	"""Remove module sections (and their nested items) from a merged Workspace
	Sidebar. Re-runnable — already-removed modules are silently skipped, so
	this can be safely called again after adjusting the list.

	Usage:
	    # hide the default list (see DEFAULT_MODULES_TO_HIDE above)
	    bench --site <site> execute india_payroll.india_payroll.scripts.customize_sidebar.hide_modules

	    # or pass your own deployment-specific list
	    bench --site <site> execute india_payroll.india_payroll.scripts.customize_sidebar.hide_modules \\
	        --kwargs "{'modules': ['Stock', 'CRM', 'Quality']}"
	"""
	target = set(modules or DEFAULT_MODULES_TO_HIDE)

	doc = frappe.get_doc("Workspace Sidebar", sidebar)
	kept = []
	skip_children = False
	removed = set()

	for row in doc.items:
		if row.type == "Section Break":
			skip_children = row.label in target
			if skip_children:
				removed.add(row.label)
				continue
			kept.append(row)
		elif skip_children and row.child:
			continue
		else:
			kept.append(row)

	doc.items = []
	for row in kept:
		doc.append("items", row)

	doc.flags.ignore_links = True
	doc.save()
	frappe.db.commit()

	print(f"Removed {len(removed)} module section(s): {', '.join(sorted(removed)) or '(none)'}")
	missing = target - removed
	if missing:
		print(f"Not found (already removed, or label mismatch?): {', '.join(sorted(missing))}")


def restore_modules(modules: list[str] | None = None, sidebar: str = "Home"):
	"""Undo hide_modules(). Reads the installed app's own home.json file — the
	source of truth, unaffected by hide_modules() unless developer_mode was on
	when it ran — rather than relying on `bench migrate`, which intentionally
	won't overwrite a DB record it considers already customized (verified:
	restoring the file via git and re-running migrate did NOT restore the DB).

	Usage:
	    # full reset: replace the sidebar with exactly what's in the file
	    bench --site <site> execute india_payroll.india_payroll.scripts.customize_sidebar.restore_modules

	    # or bring back only specific sections (appended at the end of the
	    # list rather than their original position)
	    bench --site <site> execute india_payroll.india_payroll.scripts.customize_sidebar.restore_modules \\
	        --kwargs "{'modules': ['Stock']}"
	"""
	doc = frappe.get_doc("Workspace Sidebar", sidebar)
	folder_path = create_directory_on_app_path("workspace_sidebar", doc.app)
	file_path = os.path.join(folder_path, f"{frappe.scrub(doc.title)}.json")
	with open(file_path) as f:
		source_items = json.load(f)["items"]

	if modules is None:
		# full reset — exactly what's in the file, no partial merge/ordering
		# concerns
		doc.items = []
		for item in source_items:
			doc.append("items", item)
		doc.flags.ignore_links = True
		doc.save()
		frappe.db.commit()
		print(f"Reset sidebar to the {len(source_items)} items in {file_path}")
		return

	target = set(modules)
	existing_labels = {row.label for row in doc.items if row.type == "Section Break"}

	# group the file's flat item list the same way sidebar.js's
	# find_nested_items() does: each Section Break + the child=1 rows
	# immediately following it, until the next Section Break
	groups = []
	current = None
	for item in source_items:
		if item.get("type") == "Section Break":
			current = {"header": item, "children": []}
			groups.append(current)
		elif current and item.get("child"):
			current["children"].append(item)
		else:
			current = None

	restored = set()
	for group in groups:
		label = group["header"]["label"]
		if label not in target or label in existing_labels:
			continue
		doc.append("items", group["header"])
		for child in group["children"]:
			doc.append("items", child)
		restored.add(label)

	doc.flags.ignore_links = True
	doc.save()
	frappe.db.commit()

	print(f"Restored {len(restored)} module section(s): {', '.join(sorted(restored)) or '(none)'}")
	already = target & existing_labels
	if already:
		print(f"Already present, skipped: {', '.join(sorted(already))}")
	missing = target - restored - existing_labels
	if missing:
		print(f"Not found in {file_path}: {', '.join(sorted(missing))}")

import json
import os

import frappe
from frappe.modules.utils import create_directory_on_app_path, get_doc_path

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
# Every frappe.db.commit() below carries `# nosemgrep` for
# frappe-semgrep-rules' frappe-manual-commit rule. The rule guards against
# manual commits inside request handlers, where they break the framework's
# per-request transaction. Nothing here is a request handler: these are
# one-shot maintenance entry points, run from `bench execute` or from
# india_payroll's after_migrate hook.
#
# The commit is deliberate rather than incidental. after_migrate runs near the
# end of a long migrate, and migrate rolls the whole transaction back if any
# later step raises (frappe/migrate.py:57) -- which would silently undo these
# sidebar/icon changes while leaving the rest of the migrate reported as done.
# Each function here makes one self-contained, idempotent change, so
# committing it immediately is safe and makes it durable on its own.

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
	# Frappe core admin sections. These carry no HR/Payroll dependency either,
	# but unlike the ERP modules above they are *administrator* tooling rather
	# than dead weight — hidden to keep the demo sidebar clean, not because
	# they're useless. Everything in them stays reachable via the awesomebar
	# and by direct URL; only the sidebar entry goes away. Drop a label from
	# this list (or call restore_modules with it) to bring the section back:
	#   Printing  -> Print Format, Print Heading, Print Format Builder,
	#                Print Settings  (needed to customise a payslip layout)
	#   System    -> Error Log, Scheduled Job Log/Type, RQ Job/Worker, Health
	#                Report, System Console, Recorder, Patch Log, View Log
	#                (the diagnostics you reach for when the scheduler stalls
	#                 or a payroll run fails)
	#   Website   -> Website Settings, Web Page, Web Form, Portal Settings,
	#                Website Theme, Website Script  (Website Settings is where
	#                 app_name / app_logo live, i.e. the Pratyin branding)
	"Printing",
	"System",
	"Website",
]


# Desktop Icons to hide. Deliberately NOT the same list as
# DEFAULT_MODULES_TO_HIDE above. That list governs the LEFT SIDEBAR, where a
# lean HR-only module list is wanted. These icons are the /desk launcher grid
# and the sidebar header's "Workspaces" submenu, which stay exactly as ERPNext
# ships them apart from the entries below -- hiding a module from the sidebar
# is not a reason to also strip it from the launcher. Add a label here only to
# drop it from those two places as well.
DEFAULT_ICONS_TO_HIDE = [
	"ERPNext Settings",
	# Stock and CRM are hidden everywhere else in this deployment (sidebar via
	# DEFAULT_MODULES_TO_HIDE, landing-page cards via DEFAULT_HOME_CARDS_TO_HIDE,
	# the workspaces themselves via DEFAULT_WORKSPACES_TO_HIDE), so leaving them
	# on the launcher grid and in the "Workspaces" submenu would be the one place
	# they still showed. erpnext already ships the CRM icon hidden; Stock's is
	# visible, so this is what actually removes it.
	"Stock",
	"CRM",
]


# The sidebar header icon for the merged "Home" sidebar -- the square tile next
# to the "Pratyin HRMS" subtitle.
#
# frappe resolves that tile in four steps (sidebar_header.js set_header_icon):
# a shipped SVG for the sidebar's label, then the Desktop Icon's logo_url,
# then a generated grey letter tile, and only then the configured app logo.
# The first two look the icon up through a filter that skips hidden rows, and
# erpnext ships this one hidden with no logo_url -- so both were skipped and
# the tile fell through to the letter "H". The app logo branch never runs,
# because it only applies when no Workspace Sidebar exists at all.
#
# Setting hidden=0 and logo_url makes step two resolve. Done here rather than
# by editing erpnext's desktop_icon/home.json so the whole change lives in
# this app: that file is re-imported from the erpnext fork on every migrate
# (frappe/model/sync.py:120) and after_migrate runs afterwards
# (frappe/migrate.py:200), so this wins either way.
#
# Note hidden=0 also puts a Home tile on the /desk launcher grid. The same
# flag gates both, so the logo cannot be had without it.
HOME_DESKTOP_ICON = "Home"
HOME_ICON_LOGO_URL = "/assets/india_payroll/images/pratyin-logo.png"


def set_home_icon_logo(logo_url: str | None = None, icon: str | None = None):
	"""Point the Home sidebar header icon at this app's logo.

	Called from india_payroll's after_migrate hook. Safe to re-run.

	    bench --site <site> execute india_payroll.india_payroll.scripts.customize_sidebar.set_home_icon_logo
	"""
	icon = icon or HOME_DESKTOP_ICON
	url = logo_url or HOME_ICON_LOGO_URL

	if not frappe.db.exists("Desktop Icon", icon):
		print(f"No Desktop Icon {icon!r} -- nothing to do")
		return

	current = frappe.db.get_value("Desktop Icon", icon, ["hidden", "logo_url"], as_dict=True)
	if current.hidden == 0 and current.logo_url == url:
		print(f"Desktop Icon {icon!r} already points at {url}")
		return

	# db.set_value, not doc.save(): DesktopIcon.on_update() calls
	# export_desktop_icon(), which under developer_mode rewrites the owning
	# app's JSON on disk -- here that is the erpnext fork's working tree.
	frappe.db.set_value("Desktop Icon", icon, {"hidden": 0, "logo_url": url}, update_modified=False)
	frappe.db.commit()  # nosemgrep
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
	print(f"Desktop Icon {icon!r} -> hidden=0, logo_url={url}")


def hide_desktop_icons(modules: list[str] | None = None):
	"""Hide the matching Desktop Icon records.

	This is a SEPARATE record type from what hide_modules() touches, and both
	are needed to make a module actually disappear:

	  hide_modules()       -> Workspace Sidebar "Home" -> the LEFT SIDEBAR only
	  hide_desktop_icons() -> Desktop Icon rows        -> the /desk launcher
	                          grid AND the sidebar header's "Workspaces" submenu

	Both of those read Desktop Icon and filter on `hidden`
	(frappe/desk/page/desktop/desktop.js:191 and
	frappe/public/js/frappe/ui/sidebar/sidebar_header.js:172), so a section
	removed from the sidebar alone still shows up in both places.

	Called automatically from india_payroll's after_migrate hook, so it
	re-applies on every `bench migrate` — necessary because Desktop Icon rows
	are standard records re-imported from each app's desktop_icon/ folder on
	every migrate (frappe/model/sync.py:120), which would otherwise reset
	`hidden` back to the shipped value.

	Uses frappe.db.set_value rather than doc.save() on purpose: DesktopIcon.
	on_update() calls export_desktop_icon(), which under developer_mode
	rewrites the owning app's JSON file on disk. For frappe- and hrms-owned
	icons that would dirty a working tree pinned to a release tag.
	"""
	target = modules or DEFAULT_ICONS_TO_HIDE
	hidden, missing = [], []

	for label in target:
		if not frappe.db.exists("Desktop Icon", label):
			missing.append(label)
			continue
		if not frappe.db.get_value("Desktop Icon", label, "hidden"):
			frappe.db.set_value("Desktop Icon", label, "hidden", 1, update_modified=False)
			hidden.append(label)

	frappe.db.commit()  # nosemgrep
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")

	print(f"Hid {len(hidden)} desktop icon(s): {', '.join(sorted(hidden)) or '(none, already hidden)'}")
	if missing:
		print(f"No Desktop Icon for: {', '.join(sorted(missing))}")


def show_desktop_icons(modules: list[str] | None = None):
	"""Undo hide_desktop_icons(). Note the after_migrate hook will hide them
	again on the next migrate unless the label is also removed from
	DEFAULT_ICONS_TO_HIDE.

	    bench --site <site> execute india_payroll.india_payroll.scripts.customize_sidebar.show_desktop_icons \\
	        --kwargs "{'modules': ['System']}"
	"""
	target = modules or DEFAULT_ICONS_TO_HIDE
	shown = []

	for label in target:
		if frappe.db.exists("Desktop Icon", label):
			frappe.db.set_value("Desktop Icon", label, "hidden", 0, update_modified=False)
			shown.append(label)

	frappe.db.commit()  # nosemgrep
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")
	print(f"Unhid {len(shown)} desktop icon(s): {', '.join(sorted(shown)) or '(none)'}")


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
	doc.flags.ignore_validate = True
	doc.save()
	frappe.db.commit()  # nosemgrep
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
		doc.flags.ignore_validate = True
		doc.save()
		frappe.db.commit()  # nosemgrep
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
	doc.flags.ignore_validate = True
	doc.save()
	frappe.db.commit()  # nosemgrep
	print(f"Restored {len(restored)} module section(s): {', '.join(sorted(restored)) or '(none)'}")
	already = target & existing_labels
	if already:
		print(f"Already present, skipped: {', '.join(sorted(already))}")
	missing = target - restored - existing_labels
	if missing:
		print(f"Not found in {file_path}: {', '.join(sorted(missing))}")


# -- Workspace landing page ---------------------------------------------------
# A THIRD surface, separate from both of the above. /app/home renders the
# "Home" **Workspace** (erpnext's, module "Setup"), and its `content` JSON lays
# out the "Reports & Masters" link cards: Accounting, Stock, CRM, Data Import
# and Settings. Those cards are built from the Workspace's own `links` table,
# not from the Workspace Sidebar, so a module dropped by hide_modules() still
# has its card sitting on the landing page. Verified on this bench: Stock and
# CRM were gone from the sidebar and still rendered as cards on /app/home.
#
# Hiding a card takes both halves:
#   * the `card` block removed from Workspace.content  -> the card stops being
#     laid out on the page at all
#   * hidden=1 on its Card Break row and the Link rows nested under it -> the
#     links stop being offered anywhere else that reads the links table, e.g.
#     the workspace editor's "add a card" picker
#
# Everything below uses frappe.db.set_value rather than doc.save(), for a
# sharper version of the reason given for the Desktop Icon helpers:
# Workspace.on_update() calls export_to_files() for any *public* workspace
# whenever developer_mode is on (frappe/desk/doctype/workspace/workspace.py:119)
# -- and this workspace belongs to erpnext, so a save here would rewrite
# erpnext/setup/workspace/home/home.json inside the erpnext fork's working
# tree. Staying off doc.save() keeps that file pristine, which also leaves it
# usable as the source of truth for show_home_cards() below.
#
# Re-applied from the after_migrate hook: `workspace` folders are part of what
# frappe.model.sync.sync_all() re-imports on every migrate
# (frappe/model/sync.py:19-41), so an erpnext upgrade that touches home.json
# would otherwise bring both cards back.
DEFAULT_HOME_CARDS_TO_HIDE = [
	"Stock",
	"CRM",
]


# The workspaces themselves. Marking them is_hidden=1 is what keeps /app/stock
# and /app/crm out of workspace lists, and it is also what india_payroll's
# boot_session hook keys off to strip a module from the merged Home sidebar for
# every user including Administrator (see india_payroll/boot.py). Without it a
# Workspace Manager still sees both modules offered in the workspace switcher.
DEFAULT_WORKSPACES_TO_HIDE = [
	"Stock",
	"CRM",
]


def _card_name(block: dict) -> str | None:
	"""The card a `content` block renders, or None if it is not a card block."""
	if block.get("type") != "card":
		return None
	return (block.get("data") or {}).get("card_name")


def hide_home_cards(cards: list[str] | None = None, workspace: str = "Home"):
	"""Drop link cards from a Workspace landing page. Idempotent.

	Usage:
	    # hide the default list (see DEFAULT_HOME_CARDS_TO_HIDE above)
	    bench --site <site> execute india_payroll.india_payroll.scripts.customize_sidebar.hide_home_cards

	    # or a deployment-specific list / a different workspace
	    bench --site <site> execute india_payroll.india_payroll.scripts.customize_sidebar.hide_home_cards \\
	        --kwargs "{'cards': ['Stock'], 'workspace': 'Home'}"
	"""
	target = set(cards or DEFAULT_HOME_CARDS_TO_HIDE)
	doc = frappe.get_doc("Workspace", workspace)

	# 1. the layout
	blocks = json.loads(doc.content or "[]")
	kept = [b for b in blocks if _card_name(b) not in target]
	dropped = {_card_name(b) for b in blocks if _card_name(b) in target}

	if kept != blocks:
		frappe.db.set_value("Workspace", workspace, "content", json.dumps(kept), update_modified=False)

	# 2. the links. A card is a Card Break row followed by its Link rows, until
	# the next Card Break -- the same flat-list-with-headers shape hide_modules()
	# walks for the sidebar.
	in_target_card = False
	hidden_rows = 0
	for row in doc.links:
		if row.type == "Card Break":
			in_target_card = row.label in target
		if not in_target_card or row.hidden:
			continue
		frappe.db.set_value("Workspace Link", row.name, "hidden", 1, update_modified=False)
		hidden_rows += 1

	frappe.db.commit()  # nosemgrep
	frappe.clear_document_cache("Workspace", workspace)
	frappe.cache.delete_key("bootinfo")

	print(
		f"{workspace}: removed {len(dropped)} card(s) "
		f"({', '.join(sorted(dropped)) or 'none, already removed'}) "
		f"and hid {hidden_rows} link row(s)"
	)
	missing = target - dropped
	if missing:
		print(f"Not laid out on {workspace} (already removed, or label mismatch?): {', '.join(sorted(missing))}")


def show_home_cards(cards: list[str] | None = None, workspace: str = "Home"):
	"""Undo hide_home_cards(). Note the after_migrate hook will hide them again
	on the next migrate unless the label is also removed from
	DEFAULT_HOME_CARDS_TO_HIDE.

	The card's original position in the layout is recovered from the owning app's
	shipped workspace JSON -- the source of truth, left pristine because
	hide_home_cards() never calls doc.save(). Cards that are hidden but not named
	here stay hidden.

	    bench --site <site> execute india_payroll.india_payroll.scripts.customize_sidebar.show_home_cards \\
	        --kwargs "{'cards': ['Stock']}"
	"""
	target = set(cards or DEFAULT_HOME_CARDS_TO_HIDE)
	doc = frappe.get_doc("Workspace", workspace)

	file_path = os.path.join(
		get_doc_path(doc.module, "Workspace", doc.name), f"{frappe.scrub(doc.name)}.json"
	)
	with open(file_path) as f:
		source_blocks = json.loads(json.load(f).get("content") or "[]")

	current = json.loads(doc.content or "[]")
	present = {_card_name(b) for b in current} - {None}
	still_hidden = {_card_name(b) for b in source_blocks} - {None} - present - target

	restored_content = [b for b in source_blocks if _card_name(b) not in still_hidden]
	restored = {_card_name(b) for b in source_blocks if _card_name(b) in target}

	frappe.db.set_value(
		"Workspace", workspace, "content", json.dumps(restored_content), update_modified=False
	)

	in_target_card = False
	for row in doc.links:
		if row.type == "Card Break":
			in_target_card = row.label in target
		if not in_target_card or not row.hidden:
			continue
		frappe.db.set_value("Workspace Link", row.name, "hidden", 0, update_modified=False)

	frappe.db.commit()  # nosemgrep
	frappe.clear_document_cache("Workspace", workspace)
	frappe.cache.delete_key("bootinfo")
	print(f"{workspace}: restored {len(restored)} card(s): {', '.join(sorted(restored)) or '(none)'}")


def hide_workspaces(workspaces: list[str] | None = None):
	"""Mark whole workspaces hidden, so /app/<name> stops being offered.

	Called from after_migrate -- `is_hidden` lives in the Workspace record, which
	sync_all() re-imports from the owning app's workspace/ folder on every
	migrate, so it has to be re-asserted there rather than set once by hand.

	    bench --site <site> execute india_payroll.india_payroll.scripts.customize_sidebar.hide_workspaces \\
	        --kwargs "{'workspaces': ['Stock', 'CRM']}"
	"""
	target = workspaces or DEFAULT_WORKSPACES_TO_HIDE
	hidden, missing = [], []

	for name in target:
		if not frappe.db.exists("Workspace", name):
			missing.append(name)
			continue
		if not frappe.db.get_value("Workspace", name, "is_hidden"):
			frappe.db.set_value("Workspace", name, "is_hidden", 1, update_modified=False)
			hidden.append(name)
		frappe.clear_document_cache("Workspace", name)

	frappe.db.commit()  # nosemgrep
	frappe.cache.delete_key("bootinfo")
	print(f"Hid {len(hidden)} workspace(s): {', '.join(sorted(hidden)) or '(none, already hidden)'}")
	if missing:
		print(f"No Workspace named: {', '.join(sorted(missing))}")


def show_workspaces(workspaces: list[str] | None = None):
	"""Undo hide_workspaces(). The after_migrate hook will hide them again on the
	next migrate unless the label is also removed from DEFAULT_WORKSPACES_TO_HIDE.
	"""
	target = workspaces or DEFAULT_WORKSPACES_TO_HIDE
	shown = []

	for name in target:
		if frappe.db.exists("Workspace", name):
			frappe.db.set_value("Workspace", name, "is_hidden", 0, update_modified=False)
			frappe.clear_document_cache("Workspace", name)
			shown.append(name)

	frappe.db.commit()  # nosemgrep
	frappe.cache.delete_key("bootinfo")
	print(f"Unhid {len(shown)} workspace(s): {', '.join(sorted(shown)) or '(none)'}")


# ── Help menu ────────────────────────────────────────────────────────────────
# Items in the sidebar header's Help menu come from the Navbar Settings single,
# whose help_dropdown rows are seeded from each app's `standard_help_items`
# hook. frappe ships a "Frappe Support" row pointing at frappe.io/support --
# a support channel Pratyin customers have no account for.
#
# Unlike Desktop Icon and Workspace rows, these survive a migrate: sync_table()
# in frappe/core/doctype/navbar_settings only *appends* labels it does not
# already find, so an edited row is left alone. This is still called from
# after_migrate so a fresh install and a restored site end up in the same
# state.
DEFAULT_HELP_ITEMS_TO_HIDE = [
	"Frappe Support",
]


def hide_help_items(items: list[str] | None = None):
	"""Hide rows in Navbar Settings' Help menu by label.

	`hidden` is read by SidebarHeader.get_help_siblings(), which skips the row
	before it is ever rendered, so this removes the entry rather than just
	hiding it with CSS.

	    bench --site <site> execute india_payroll.india_payroll.scripts.customize_sidebar.hide_help_items \
	        --kwargs "{'items': ['Frappe Support']}"
	"""
	target = items or DEFAULT_HELP_ITEMS_TO_HIDE
	hidden, missing = [], []

	for label in target:
		rows = frappe.get_all(
			"Navbar Item",
			filters={
				"parent": "Navbar Settings",
				"parenttype": "Navbar Settings",
				"parentfield": "help_dropdown",
				"item_label": label,
			},
			pluck="name",
		)
		if not rows:
			missing.append(label)
			continue
		for name in rows:
			if not frappe.db.get_value("Navbar Item", name, "hidden"):
				frappe.db.set_value("Navbar Item", name, "hidden", 1, update_modified=False)
				hidden.append(label)

	frappe.db.commit()  # nosemgrep
	frappe.clear_document_cache("Navbar Settings", "Navbar Settings")
	frappe.cache.delete_key("bootinfo")
	print(f"Hid {len(hidden)} help item(s): {', '.join(sorted(hidden)) or '(none, already hidden)'}")
	if missing:
		print(f"No Help menu item named: {', '.join(sorted(missing))}")


def show_help_items(items: list[str] | None = None):
	"""Undo hide_help_items(). The after_migrate hook will hide them again on the
	next migrate unless the label is also removed from DEFAULT_HELP_ITEMS_TO_HIDE.
	"""
	target = items or DEFAULT_HELP_ITEMS_TO_HIDE
	shown = []

	for label in target:
		rows = frappe.get_all(
			"Navbar Item",
			filters={
				"parent": "Navbar Settings",
				"parenttype": "Navbar Settings",
				"parentfield": "help_dropdown",
				"item_label": label,
			},
			pluck="name",
		)
		for name in rows:
			frappe.db.set_value("Navbar Item", name, "hidden", 0, update_modified=False)
			shown.append(label)

	frappe.db.commit()  # nosemgrep
	frappe.clear_document_cache("Navbar Settings", "Navbar Settings")
	frappe.cache.delete_key("bootinfo")
	print(f"Unhid {len(shown)} help item(s): {', '.join(sorted(shown)) or '(none)'}")

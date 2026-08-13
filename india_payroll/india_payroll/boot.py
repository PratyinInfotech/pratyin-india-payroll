import frappe


def filter_hidden_workspaces(bootinfo) -> None:
	"""
	boot_session hook — runs after core boot info (including the merged Home
	Workspace Sidebar) is built.

	Stock Frappe's Workspace.is_hidden is only enforced for users without the
	"Workspace Manager" role — Administrator and Workspace Managers always see
	hidden workspaces so they can un-hide them. That's fine for the normal
	per-workspace sidebar, but this deployment merges every module into one
	always-visible "Home" sidebar, so a module marked Hidden needs to actually
	disappear for everyone, including Administrator. Strip those links (and
	any section that ends up with no children left) from every sidebar here,
	unconditionally.
	"""
	sidebars = bootinfo.get("workspace_sidebar_item")
	if not sidebars:
		return

	hidden_workspaces = set(frappe.get_all("Workspace", filters={"is_hidden": 1}, pluck="name"))
	if not hidden_workspaces:
		return

	for sidebar in sidebars.values():
		items = sidebar.get("items")
		if items:
			sidebar["items"] = _drop_hidden_items(items, hidden_workspaces)


def _drop_hidden_items(items: list[dict], hidden_workspaces: set[str]) -> list[dict]:
	# A module's Section Break is a separate row from the "Workspace"-linked
	# item nested inside it (that inner item is the self-navigation link,
	# generically labeled "Home"). Filtering only that inner link removes the
	# ability to jump straight to the module's landing page, but leaves the
	# section heading and every other child (doctype/report/list links) fully
	# visible and clickable — which is what a module marked Hidden must not
	# do. The Section Break's own label matches the Workspace's name for
	# every module built from the Desktop Icon tree, so that's the signal
	# used to drop the whole section, header and all.
	kept = []
	skip_section = False
	section_child_count = {}
	current_section_id = None

	for item in items:
		if item.get("type") == "Section Break":
			skip_section = item.get("label") in hidden_workspaces
			if skip_section:
				continue
			current_section_id = id(item)
			section_child_count[current_section_id] = 0
			kept.append(item)
			continue

		if skip_section:
			continue

		if item.get("link_type") == "Workspace" and item.get("link_to") in hidden_workspaces:
			continue

		if current_section_id is not None and item.get("child"):
			section_child_count[current_section_id] += 1
		kept.append(item)

	# Safety net: a section can also end up empty purely from the individual
	# link filter above (e.g. its only child happened to be a link to some
	# other hidden workspace) even though its own label didn't match.
	return [
		item
		for item in kept
		if item.get("type") != "Section Break" or section_child_count.get(id(item), 0) > 0
	]

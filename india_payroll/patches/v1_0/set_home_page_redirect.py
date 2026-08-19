import frappe


def execute():
	"""
	Point the desk landing page at the custom `home-redirect` page so users land
	on the merged Home workspace sidebar instead of the classic /desk grid.

	This is a global Default Value (`desktop:home_page`), which lives only in
	the site database — it doesn't travel via `git pull` like code does, so it
	has to be set explicitly here on every site that installs this app.
	"""
	frappe.db.set_default("desktop:home_page", "home-redirect")

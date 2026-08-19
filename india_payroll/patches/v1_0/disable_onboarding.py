import frappe


def execute():
	"""
	Turn off the built-in "Getting Started" onboarding popups site-wide.

	`System Settings.enable_onboarding` is a global site setting, not code, so
	it doesn't travel via `git pull` — every module in the merged Home sidebar
	that has an incomplete Module Onboarding record (e.g. Stock) can otherwise
	pop up its onboarding panel on unrelated pages. Disable it explicitly here,
	same fix pattern as the home-page redirect default.
	"""
	frappe.db.set_single_value("System Settings", "enable_onboarding", 0)

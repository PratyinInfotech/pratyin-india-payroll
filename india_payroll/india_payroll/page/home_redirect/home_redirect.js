// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

// Landing page target for `desktop:home_page` — skips the Desktop app-picker
// grid and drops the user straight into the merged "Home" workspace sidebar.
frappe.pages["home-redirect"].on_page_load = function () {
	frappe.route_flags.replace_route = true;
	frappe.set_route("home");
};

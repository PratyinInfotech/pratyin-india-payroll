// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings["Salary Structure Assignment"] = {
	onload: function (listview) {
		if (
			!has_common(frappe.user_roles, [
				"Administrator",
				"System Manager",
				"HR Manager",
				"HR User",
			])
		)
			return;

		listview.page.add_menu_item(__("Notify Employees to Select Tax Regime"), () => {
			if (!listview.get_checked_items().length) {
				frappe.msgprint(__("Please select at least one Salary Structure Assignment"));
				return;
			}
			listview.call_for_selected_items(
				"india_payroll.india_payroll.page.tax_regime_selector.tax_regime_selector.notify_employees_to_select_tax_regime"
			);
		});
	},
};

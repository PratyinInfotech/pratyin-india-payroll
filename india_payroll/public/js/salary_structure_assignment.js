// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Salary Structure Assignment", {
	refresh(frm) {
		// Draft, saved assignments only (the tax regime can only be changed while draft).
		if (frm.is_new() || frm.doc.docstatus !== 0 || !frm.doc.employee) return;

		frm.add_custom_button(__("Notify Employee to Select Tax Regime"), () => {
			frappe.call({
				method: "india_payroll.india_payroll.page.tax_regime_selector.tax_regime_selector.notify_employee_to_select_tax_regime",
				args: { assignment: frm.doc.name },
				freeze: true,
				freeze_message: __("Sending…"),
				callback: (r) => {
					if (r.message?.sent) {
						frappe.show_alert({
							message: __("Email sent to {0}", [r.message.email]),
							indicator: "green",
						});
					}
				},
			});
		});
	},
});

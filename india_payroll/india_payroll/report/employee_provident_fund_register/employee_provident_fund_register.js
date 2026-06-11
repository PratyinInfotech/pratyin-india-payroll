// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

const MONTHS = [
	"January",
	"February",
	"March",
	"April",
	"May",
	"June",
	"July",
	"August",
	"September",
	"October",
	"November",
	"December",
];

function _yearOptions() {
	const current = new Date().getFullYear();
	const options = [];
	for (let y = current - 3; y <= current + 1; y++) options.push(String(y));
	return options.join("\n");
}

frappe.query_reports["Employee Provident Fund Register"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Select",
			options: _yearOptions(),
			default: String(new Date().getFullYear()),
			reqd: 1,
		},
		{
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			options: "\n" + MONTHS.join("\n"),
			default: MONTHS[new Date().getMonth()],
		},
		{
			fieldname: "contribution_period",
			label: __("Contribution Period"),
			fieldtype: "Select",
			options: "\nApr-Sep\nOct-Mar",
			description: __("Overrides the Month filter when set"),
		},
	],

	onload(report) {
		report.page.add_inner_button(__("Download ECR Text File"), () => {
			const filters = frappe.query_report.get_values();
			frappe.call({
				method:
					"india_payroll.india_payroll.report.employee_provident_fund_register" +
					".employee_provident_fund_register.get_ecr_file",
				args: { filters },
				freeze: true,
				freeze_message: __("Generating ECR file…"),
				callback(r) {
					const out = r.message || {};
					if (!out.content) {
						frappe.msgprint(__("No EPF-eligible rows for the selected period."));
						return;
					}
					const blob = new Blob([out.content], {
						type: "text/plain;charset=utf-8;",
					});
					const url = URL.createObjectURL(blob);
					const a = document.createElement("a");
					a.href = url;
					a.download = out.filename || "ECR.txt";
					a.click();
					URL.revokeObjectURL(url);
					frappe.show_alert({
						message: __("Exported {0} member(s) to ECR file.", [out.row_count]),
						indicator: "green",
					});
				},
			});
		});
	},
};

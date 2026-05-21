# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 120,
		},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
		{
			"label": _("Department"),
			"fieldname": "department",
			"fieldtype": "Link",
			"options": "Department",
			"width": 150,
		},
		{
			"label": _("Designation"),
			"fieldname": "designation",
			"fieldtype": "Link",
			"options": "Designation",
			"width": 150,
		},
		{"label": _("Bank Name"), "fieldname": "bank_name", "fieldtype": "Data", "width": 150},
		{"label": _("Account Number"), "fieldname": "bank_ac_no", "fieldtype": "Data", "width": 160},
		{"label": _("IFSC Code"), "fieldname": "ifsc_code", "fieldtype": "Data", "width": 120},
		{"label": _("MICR Code"), "fieldname": "micr_code", "fieldtype": "Data", "width": 120},
		{"label": _("Payment Mode"), "fieldname": "salary_mode", "fieldtype": "Data", "width": 120},
		{
			"label": _("Net Pay"),
			"fieldname": "net_pay",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140,
		},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 60, "hidden": 1},
	]


def get_data(filters):
	SS = DocType("Salary Slip")
	Emp = DocType("Employee")

	query = (
		frappe.qb.from_(SS)
		.join(Emp)
		.on(Emp.name == SS.employee)
		.select(
			SS.employee,
			SS.employee_name,
			Emp.department,
			Emp.designation,
			Emp.bank_name,
			Emp.bank_ac_no,
			Emp.salary_mode,
			SS.net_pay,
		)
		.where(SS.docstatus == 1)
	)

	if filters.get("company"):
		query = query.where(SS.company == filters["company"])

	if filters.get("from_date"):
		query = query.where(SS.start_date >= filters["from_date"])

	if filters.get("to_date"):
		query = query.where(SS.end_date <= filters["to_date"])

	if filters.get("department"):
		query = query.where(Emp.department == filters["department"])

	if filters.get("salary_mode"):
		query = query.where(Emp.salary_mode == filters["salary_mode"])

	rows = query.orderby(Emp.department).orderby(SS.employee_name).run(as_dict=True)

	# Fetch IFSC and MICR codes (added as custom fields by india_payroll)
	has_ifsc = frappe.db.has_column("Employee", "ifsc_code")
	has_micr = frappe.db.has_column("Employee", "micr_code")

	if rows and (has_ifsc or has_micr):
		emp_names = list({r.employee for r in rows})
		fields = ["name"]
		if has_ifsc:
			fields.append("ifsc_code")
		if has_micr:
			fields.append("micr_code")

		emp_details = frappe.get_all("Employee", filters={"name": ["in", emp_names]}, fields=fields)
		emp_map = {e.name: e for e in emp_details}

		for row in rows:
			emp = emp_map.get(row.employee, frappe._dict())
			row["ifsc_code"] = emp.get("ifsc_code") or ""
			row["micr_code"] = emp.get("micr_code") or ""
	else:
		for row in rows:
			row["ifsc_code"] = ""
			row["micr_code"] = ""

	currency = ""
	if filters.get("company"):
		currency = frappe.get_cached_value("Company", filters["company"], "default_currency") or ""

	for row in rows:
		row["net_pay"] = flt(row.get("net_pay"), 2)
		row["currency"] = currency

	return rows

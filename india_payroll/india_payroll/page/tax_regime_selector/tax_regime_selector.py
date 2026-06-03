# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from datetime import date

import frappe
from frappe.utils import flt, getdate
from hrms.payroll.doctype.income_tax_slab.income_tax_slab import calculate_tax_by_tax_slab

from india_payroll.india_payroll.tax_exemption_setup import setup_tax_exemption_categories

OLD_REGIME_SLAB = "Old Tax Regime: 2019"
NEW_REGIME_SLAB = "New Tax Regime: 2025-2026"

SECTION_CAPS = {
	"80CCD(1B)": 50000,
	"80D": 75000,
	"80DD": 125000,
	"80DDB": 100000,
	"80EE": 50000,
	"80EEA": 150000,
	"24": 200000,
	"80GG": 60000,
	"80TTA": 10000,
	"80TTB": 50000,
	"80U": 125000,
}


@frappe.whitelist()
def setup_if_missing() -> dict:
	"""Idempotently create income tax slabs and exemption categories."""
	from india_payroll.install import create_income_tax_slabs

	create_income_tax_slabs()

	if not frappe.db.count("Employee Tax Exemption Category"):
		setup_tax_exemption_categories()

	return {"ok": True}


@frappe.whitelist()
def get_employee_details(employee: str) -> dict:
	data = get_employee_salary_data(employee)

	cats = frappe.get_all(
		"Employee Tax Exemption Category",
		fields=["name", "max_amount", "description"],
		order_by="name",
	)
	if not cats:
		setup_tax_exemption_categories()
		cats = frappe.get_all(
			"Employee Tax Exemption Category",
			fields=["name", "max_amount", "description"],
			order_by="name",
		)

	cat_list = []
	for cat in cats:
		subs = frappe.get_all(
			"Employee Tax Exemption Sub Category",
			filters={"exemption_category": cat.name},
			fields=["name", "max_amount"],
			order_by="name",
		)
		cat_list.append(
			{
				"name": cat.name,
				"max_amount": cat.max_amount,
				"description": cat.description,
				"sub_categories": [{"name": s.name, "max_amount": s.max_amount} for s in subs],
			}
		)

	data["exemption_categories"] = cat_list

	company = frappe.db.get_value("Employee", employee, "company")
	today = frappe.utils.today()
	payroll_period = frappe.db.get_value(
		"Payroll Period",
		{"company": company, "start_date": ("<=", today), "end_date": (">=", today)},
		"name",
	)
	data["payroll_period"] = payroll_period or None
	return data


@frappe.whitelist()
def get_current_payroll_period() -> dict:
	company = frappe.defaults.get_global_default("company")
	today = frappe.utils.today()
	period = frappe.db.get_value(
		"Payroll Period",
		{"company": company, "start_date": ("<=", today), "end_date": (">=", today)},
		"name",
	)
	return {"payroll_period": period or None}


@frappe.whitelist()
def compute_tax_comparison(
	employee: str,
	declarations: dict | str,
	rent_monthly: float = 0,
	city_type: str = "non-metro",
	annual_gross: float = 0,
) -> dict:
	if isinstance(declarations, str):
		declarations = frappe.parse_json(declarations)

	data = get_employee_salary_data(employee)
	if flt(annual_gross):
		data["annual_gross"] = flt(annual_gross)

	old_taxable, old_breakdown = compute_old_regime(data, declarations, flt(rent_monthly), city_type)
	new_taxable, new_breakdown = compute_new_regime(data)

	old_slab = frappe.get_doc("Income Tax Slab", OLD_REGIME_SLAB)
	new_slab = frappe.get_doc("Income Tax Slab", NEW_REGIME_SLAB)

	old_tax, _ = calculate_tax_by_tax_slab(old_taxable, old_slab)
	new_tax, _ = calculate_tax_by_tax_slab(new_taxable, new_slab)

	return {
		"old_regime": {
			"slab": OLD_REGIME_SLAB,
			"taxable_income": old_taxable,
			"tax": old_tax,
			"breakdown": old_breakdown,
		},
		"new_regime": {
			"slab": NEW_REGIME_SLAB,
			"taxable_income": new_taxable,
			"tax": new_tax,
			"breakdown": new_breakdown,
		},
		"recommended": "old" if old_tax < new_tax else "new",
		"savings": abs(old_tax - new_tax),
	}


@frappe.whitelist()
def set_tax_regime(employee: str, income_tax_slab: str) -> None:
	name = frappe.db.get_value(
		"Salary Structure Assignment",
		{"employee": employee, "docstatus": 1},
		"name",
		order_by="from_date desc",
	)
	if not name:
		frappe.throw(frappe._("No active Salary Structure Assignment found for {0}").format(employee))
	frappe.db.set_value("Salary Structure Assignment", name, "income_tax_slab", income_tax_slab)


def evaluate_annual_gross(doc, method=None):
	"""Compute annual gross from earning components and save to the assignment."""
	base = flt(doc.base)
	structure = frappe.get_doc("Salary Structure", doc.salary_structure)
	monthly_gross = sum(
		evaluate_component(row, base) for row in structure.earnings if not row.statistical_component
	)
	frappe.db.set_value("Salary Structure Assignment", doc.name, "annual_gross_earning", monthly_gross * 12)


def get_employee_salary_data(employee):
	assignment = frappe.db.get_value(
		"Salary Structure Assignment",
		{"employee": employee, "docstatus": 1},
		["name", "salary_structure", "base", "income_tax_slab", "annual_gross_earning"],
		order_by="from_date desc",
		as_dict=True,
	)
	if not assignment:
		frappe.throw(frappe._("No active Salary Structure Assignment found for {0}").format(employee))

	base = flt(assignment.base)
	structure = frappe.get_doc("Salary Structure", assignment.salary_structure)

	monthly_gross = 0
	monthly_hra = 0
	monthly_lta = 0
	monthly_employer_nps = 0

	for row in structure.earnings:
		if row.statistical_component:
			continue
		amount = evaluate_component(row, base)
		monthly_gross += amount
		abbr = (row.abbr or "").upper()
		if abbr == "HRA":
			monthly_hra = amount
		elif abbr == "LTA":
			monthly_lta = amount

	for row in structure.deductions:
		component_name = (row.salary_component or "").upper()
		if "NPS" in component_name and "EMPLOYER" in component_name:
			monthly_employer_nps = evaluate_component(row, base)

	# Prefer stored annual_gross_earning; fall back to calculation then latest slip
	if flt(assignment.annual_gross_earning):
		annual_gross = flt(assignment.annual_gross_earning)
	else:
		slip_gross = frappe.db.get_value(
			"Salary Slip",
			{"employee": employee, "docstatus": 1},
			"gross_pay",
			order_by="posting_date desc",
		)
		annual_gross = flt(slip_gross) * 12 if slip_gross else monthly_gross * 12

	emp_dob = frappe.db.get_value("Employee", employee, "date_of_birth")

	return {
		"annual_gross": annual_gross,
		"annual_basic": base * 12,
		"annual_hra": monthly_hra * 12,
		"annual_lta": monthly_lta * 12,
		"annual_employer_nps": monthly_employer_nps * 12,
		"has_hra": monthly_hra > 0,
		"is_senior_citizen": check_senior_citizen(emp_dob),
		"current_income_tax_slab": assignment.income_tax_slab,
	}


def evaluate_component(row, base):
	if row.amount_based_on_formula:
		try:
			return flt(frappe.safe_eval(row.formula, {"base": base}))
		except Exception:
			return 0
	return flt(row.amount)


def check_senior_citizen(date_of_birth):
	if not date_of_birth:
		return False
	today = date.today()
	fy_start = date(today.year if today.month >= 4 else today.year - 1, 4, 1)
	dob = getdate(date_of_birth)
	age = fy_start.year - dob.year - ((dob.month, dob.day) > (fy_start.month, fy_start.day))
	return age >= 60


def compute_old_regime(data, declarations, rent_monthly, city_type):
	gross = data["annual_gross"]
	basic = data["annual_basic"]
	standard_deduction = 50000

	hra_exemption = 0
	if data["has_hra"] and rent_monthly > 0:
		hra_exemption = compute_hra_exemption(data["annual_hra"], basic, rent_monthly, city_type)

	lta_exemption = data["annual_lta"]
	employer_nps = min(data["annual_employer_nps"], basic * 0.10)
	via = compute_via_deductions(declarations, data)
	via_total = sum(via.values())

	taxable = max(0, gross - standard_deduction - hra_exemption - lta_exemption - employer_nps - via_total)

	return taxable, {
		"gross": gross,
		"standard_deduction": standard_deduction,
		"hra_exemption": hra_exemption,
		"lta_exemption": lta_exemption,
		"employer_nps": employer_nps,
		"via_deductions": via,
		"taxable_income": taxable,
	}


def compute_new_regime(data):
	gross = data["annual_gross"]
	basic = data["annual_basic"]
	standard_deduction = 75000
	employer_nps = min(data["annual_employer_nps"], basic * 0.10)

	taxable = max(0, gross - standard_deduction - employer_nps)

	return taxable, {
		"gross": gross,
		"standard_deduction": standard_deduction,
		"employer_nps": employer_nps,
		"taxable_income": taxable,
	}


def compute_hra_exemption(annual_hra, annual_basic, rent_monthly, city_type):
	annual_rent = rent_monthly * 12
	metro_percent = 0.50 if city_type == "metro" else 0.40
	return max(
		0,
		min(
			annual_hra,
			metro_percent * annual_basic,
			annual_rent - 0.10 * annual_basic,
		),
	)


def compute_via_deductions(declarations, data):
	deductions = {}

	# 80CCE combined cap: 80C + 80CCC + 80CCD(1)
	cce = min(
		flt(declarations.get("80C", 0))
		+ flt(declarations.get("80CCC", 0))
		+ flt(declarations.get("80CCD(1)", 0)),
		150000,
	)
	if cce:
		deductions["80CCE (80C + 80CCC + 80CCD(1))"] = cce

	# Sections with statutory caps
	for section, cap in SECTION_CAPS.items():
		if section == "80GG" and data["has_hra"]:
			continue
		amount = flt(declarations.get(section, 0))
		if amount:
			deductions[section] = min(amount, cap)

	# No-cap sections
	for section in ("80E", "80G", "80GGC"):
		amount = flt(declarations.get(section, 0))
		if amount:
			deductions[section] = amount

	return deductions

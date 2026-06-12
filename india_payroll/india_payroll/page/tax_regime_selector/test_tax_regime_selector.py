# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from erpnext.setup.doctype.employee.test_employee import make_employee
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from hrms.payroll.doctype.salary_structure.test_salary_structure import (
	create_salary_structure_assignment,
	make_salary_structure,
)
from hrms.tests.utils import HRMSTestSuite

from india_payroll.india_payroll.page.tax_regime_selector.tax_regime_selector import (
	NEW_REGIME_SLAB,
	OLD_REGIME_SLAB,
	build_prefill_declarations,
	compute_tax_comparison,
	get_employee_details,
	get_employee_salary_data,
	set_tax_regime,
)
from india_payroll.india_payroll.tax_exemption_setup import setup_tax_exemption_categories
from india_payroll.install import create_income_tax_slabs, get_custom_fields

COMPANY = "_Test Company"

# base * 12 earnings: Basic = base, HRA = base / 2 -> monthly gross = 1.5 * base
EARNINGS = [
	{
		"salary_component": "Basic Salary",
		"abbr": "BS",
		"formula": "base",
		"type": "Earning",
		"amount_based_on_formula": 1,
	},
	{
		"salary_component": "House Rent Allowance",
		"abbr": "HRA",
		"formula": "base / 2",
		"type": "Earning",
		"amount_based_on_formula": 1,
	},
]


def ensure_salary_components():
	for name, abbr, ctype in (
		("Basic Salary", "BS", "Earning"),
		("House Rent Allowance", "HRA", "Earning"),
		("Employee Provident Fund", "PF", "Deduction"),
	):
		if not frappe.db.exists("Salary Component", name):
			frappe.get_doc(
				{
					"doctype": "Salary Component",
					"salary_component": name,
					"salary_component_abbr": abbr,
					"type": ctype,
				}
			).insert()


DEDUCTIONS = [
	{
		"salary_component": "Employee Provident Fund",
		"abbr": "PF",
		"amount": 1800,
		"type": "Deduction",
	},
]


def make_structure(employee, base, from_date="2026-04-01"):
	ensure_salary_components()
	structure = make_salary_structure(
		"IP Tax Regime Test Structure",
		"Monthly",
		employee=employee,
		company=COMPANY,
		currency="INR",
		from_date=from_date,
		base=base,
		earnings=EARNINGS,
		deductions=DEDUCTIONS,
	)
	return structure


class TestTaxRegimeSelector(HRMSTestSuite):
	def setUp(self):
		create_custom_fields(get_custom_fields())
		create_income_tax_slabs()
		setup_tax_exemption_categories()

	def test_annual_gross_sourced_from_assignment(self):
		"""get_employee_salary_data reads the SSA's computed annual_gross_earning."""
		employee = make_employee("ip_trs_gross@indiapayroll.com", company=COMPANY)
		make_structure(employee, base=100000)

		ssa = frappe.db.get_value(
			"Salary Structure Assignment",
			{"employee": employee, "docstatus": 1},
			["name", "annual_gross_earning"],
			as_dict=True,
		)
		self.assertTrue(ssa.annual_gross_earning)

		data = get_employee_salary_data(employee)
		self.assertEqual(data["annual_gross"], ssa.annual_gross_earning)
		# Basic + HRA = 1.5 * base * 12
		self.assertEqual(data["annual_gross"], 100000 * 1.5 * 12)
		self.assertTrue(data["has_hra"])
		self.assertEqual(data["annual_hra"], 50000 * 12)

	def test_regime_comparison_returns_recommendation(self):
		employee = make_employee("ip_trs_compare@indiapayroll.com", company=COMPANY)
		make_structure(employee, base=100000)

		result = compute_tax_comparison(employee, declarations={})
		self.assertIn(result["recommended"], ("old", "new"))
		self.assertEqual(
			result["savings"],
			abs(result["old_regime"]["tax"] - result["new_regime"]["tax"]),
		)
		# With no declarations, the new regime (higher standard deduction, lower
		# slabs) should win for this salary.
		self.assertEqual(result["recommended"], "new")

	def test_hra_exemption_applied_in_old_regime(self):
		employee = make_employee("ip_trs_hra@indiapayroll.com", company=COMPANY)
		make_structure(employee, base=100000)

		result = compute_tax_comparison(
			employee,
			declarations={},
			rent_monthly=40000,
			city_type="metro",
		)
		breakdown = result["old_regime"]["breakdown"]
		# min(annual_hra=600000, 50% basic=600000, rent 480000 - 10% basic 120000=360000)
		self.assertEqual(breakdown["hra_exemption"], 360000)

		# New regime ignores HRA entirely.
		self.assertNotIn("hra_exemption", result["new_regime"]["breakdown"])

	def test_80cce_combined_cap(self):
		employee = make_employee("ip_trs_80c@indiapayroll.com", company=COMPANY)
		make_structure(employee, base=100000)

		result = compute_tax_comparison(employee, declarations={"80C": 200000})
		via = result["old_regime"]["breakdown"]["via_deductions"]
		cce = next(v for k, v in via.items() if k.startswith("80CCE"))
		self.assertEqual(cce, 150000)

	def test_prefill_fuzzy_match(self):
		"""Statutory deductions fuzzy-match exemption sub-categories by name."""
		cat_list = [
			{"name": "80C", "sub_categories": [{"name": "Employee Provident Fund (EPF)"}]},
			{"name": "80CCD(1)", "sub_categories": [{"name": "Employee NPS Contribution - 80CCD(1)"}]},
		]
		deductions = [
			{"component": "Employee Provident Fund", "annual_amount": 21600},
			{"component": "Professional Tax", "annual_amount": 2400},  # no match
		]
		prefill = build_prefill_declarations(deductions, cat_list)
		self.assertEqual(prefill, {"80C": {"Employee Provident Fund (EPF)": 21600}})

	def test_prefill_via_get_employee_details(self):
		employee = make_employee("ip_trs_prefill@indiapayroll.com", company=COMPANY)
		make_structure(employee, base=100000)

		data = get_employee_details(employee)
		# EPF deduction of 1800/month -> 21600/year, matched to 80C EPF sub.
		self.assertEqual(data["prefill_declarations"]["80C"]["Employee Provident Fund (EPF)"], 1800 * 12)

	def test_senior_citizen_flag(self):
		employee = make_employee(
			"ip_trs_senior@indiapayroll.com",
			company=COMPANY,
			date_of_birth="1960-01-01",
		)
		make_structure(employee, base=100000)

		data = get_employee_salary_data(employee)
		self.assertTrue(data["is_senior_citizen"])

	def test_set_tax_regime_blocked_when_submitted(self):
		employee = make_employee("ip_trs_submitted@indiapayroll.com", company=COMPANY)
		make_structure(employee, base=100000)  # submitted SSA

		self.assertRaises(frappe.ValidationError, set_tax_regime, employee, NEW_REGIME_SLAB)

	def test_set_tax_regime_allowed_when_draft(self):
		employee = make_employee("ip_trs_draft@indiapayroll.com", company=COMPANY)
		ensure_salary_components()
		# Structure only (no auto-assignment), then a DRAFT assignment.
		make_salary_structure(
			"IP Tax Regime Test Structure",
			"Monthly",
			company=COMPANY,
			currency="INR",
			earnings=EARNINGS,
			deductions=DEDUCTIONS,
		)
		ssa = frappe.get_doc(
			{
				"doctype": "Salary Structure Assignment",
				"employee": employee,
				"salary_structure": "IP Tax Regime Test Structure",
				"from_date": "2026-04-01",
				"base": 100000,
				"company": COMPANY,
				"currency": "INR",
				"income_tax_slab": OLD_REGIME_SLAB,
			}
		).insert()  # draft (docstatus 0)

		result = set_tax_regime(employee, NEW_REGIME_SLAB)
		self.assertEqual(result["assignment"], ssa.name)
		self.assertEqual(
			frappe.db.get_value("Salary Structure Assignment", ssa.name, "income_tax_slab"),
			NEW_REGIME_SLAB,
		)

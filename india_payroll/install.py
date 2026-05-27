import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from india_payroll.india_payroll.tax_exemption_setup import setup_tax_exemption_categories

INDIA_STATES = [
	"Andhra Pradesh",
	"Arunachal Pradesh",
	"Assam",
	"Bihar",
	"Chhattisgarh",
	"Goa",
	"Gujarat",
	"Haryana",
	"Himachal Pradesh",
	"Jharkhand",
	"Karnataka",
	"Kerala",
	"Madhya Pradesh",
	"Maharashtra",
	"Manipur",
	"Meghalaya",
	"Mizoram",
	"Nagaland",
	"Odisha",
	"Punjab",
	"Rajasthan",
	"Sikkim",
	"Tamil Nadu",
	"Telangana",
	"Tripura",
	"Uttar Pradesh",
	"Uttarakhand",
	"West Bengal",
	"Andaman and Nicobar Islands",
	"Chandigarh",
	"Dadra and Nagar Haveli and Daman and Diu",
	"Delhi",
	"Jammu and Kashmir",
	"Ladakh",
	"Lakshadweep",
	"Puducherry",
]


SURCHARGE_NEW_REGIME = [
	{
		"description": "Surcharge 10%",
		"percent": 10,
		"min_taxable_income": 5000001,
		"max_taxable_income": 10000000,
	},
	{
		"description": "Surcharge 15%",
		"percent": 15,
		"min_taxable_income": 10000001,
		"max_taxable_income": 20000000,
	},
	{"description": "Surcharge 25%", "percent": 25, "min_taxable_income": 20000001, "max_taxable_income": 0},
]

SURCHARGE_OLD_REGIME = [
	{
		"description": "Surcharge 10%",
		"percent": 10,
		"min_taxable_income": 5000001,
		"max_taxable_income": 10000000,
	},
	{
		"description": "Surcharge 15%",
		"percent": 15,
		"min_taxable_income": 10000001,
		"max_taxable_income": 20000000,
	},
	{
		"description": "Surcharge 25%",
		"percent": 25,
		"min_taxable_income": 20000001,
		"max_taxable_income": 50000000,
	},
	{"description": "Surcharge 37%", "percent": 37, "min_taxable_income": 50000001, "max_taxable_income": 0},
]

CESS = [
	{
		"description": "Health & Education Cess",
		"percent": 4,
		"min_taxable_income": 0,
		"max_taxable_income": 0,
	},
]


INDIA_TAX_SLABS = {
	"Old Tax Regime: 2019": {
		"effective_from": "2019-04-01",
		"currency": "INR",
		"allow_tax_exemption": 1,
		"standard_tax_exemption_amount": 50000,
		"tax_relief_limit": 500000,
		"marginal_relief_limit": 512500,
		"slabs": [
			{"from_amount": 0, "to_amount": 250000, "percent_deduction": 0},
			{"from_amount": 250001, "to_amount": 500000, "percent_deduction": 5},
			{"from_amount": 500001, "to_amount": 1000000, "percent_deduction": 20},
			{"from_amount": 1000001, "to_amount": 0, "percent_deduction": 30},
		],
		"surcharge_slabs": SURCHARGE_OLD_REGIME,
		"other_taxes_and_charges": CESS,
	},
	"New Tax Regime: 2024-2025": {
		"effective_from": "2024-04-01",
		"currency": "INR",
		"allow_tax_exemption": 0,
		"standard_tax_exemption_amount": 75000,
		"tax_relief_limit": 700000,
		"marginal_relief_limit": 727777,
		"slabs": [
			{"from_amount": 0, "to_amount": 300000, "percent_deduction": 0},
			{"from_amount": 300001, "to_amount": 700000, "percent_deduction": 5},
			{"from_amount": 700001, "to_amount": 1000000, "percent_deduction": 10},
			{"from_amount": 1000001, "to_amount": 1200000, "percent_deduction": 15},
			{"from_amount": 1200001, "to_amount": 1500000, "percent_deduction": 20},
			{"from_amount": 1500001, "to_amount": 0, "percent_deduction": 30},
		],
		"surcharge_slabs": SURCHARGE_NEW_REGIME,
		"other_taxes_and_charges": CESS,
	},
	"New Tax Regime: 2025-2026": {
		"effective_from": "2025-04-01",
		"currency": "INR",
		"allow_tax_exemption": 0,
		"standard_tax_exemption_amount": 75000,
		"tax_relief_limit": 1200000,
		"marginal_relief_limit": 1275000,
		"slabs": [
			{"from_amount": 0, "to_amount": 400000, "percent_deduction": 0},
			{"from_amount": 400001, "to_amount": 800000, "percent_deduction": 5},
			{"from_amount": 800001, "to_amount": 1200000, "percent_deduction": 10},
			{"from_amount": 1200001, "to_amount": 1600000, "percent_deduction": 15},
			{"from_amount": 1600001, "to_amount": 2000000, "percent_deduction": 20},
			{"from_amount": 2000001, "to_amount": 2400000, "percent_deduction": 25},
			{"from_amount": 2400001, "to_amount": 0, "percent_deduction": 30},
		],
		"surcharge_slabs": SURCHARGE_NEW_REGIME,
		"other_taxes_and_charges": CESS,
	},
}


def get_custom_fields():
	return {
		"Payroll Settings": [
			{
				"fieldname": "india_payroll_tab",
				"label": "India Payroll",
				"fieldtype": "Tab Break",
				"insert_after": "create_overtime_slip",
			},
			{
				"fieldname": "india_payroll_professional_tax_section",
				"label": "Professional Tax",
				"fieldtype": "Section Break",
				"insert_after": "india_payroll_tab",
			},
			{
				"fieldname": "enable_professional_tax",
				"label": "Enable Professional Tax Deduction",
				"fieldtype": "Check",
				"insert_after": "india_payroll_professional_tax_section",
			},
			{
				"fieldname": "india_payroll_esic_section",
				"label": "Employee State Insurance",
				"fieldtype": "Section Break",
				"insert_after": "enable_professional_tax",
			},
			{
				"fieldname": "enable_esic",
				"label": "Enable ESIC Deduction",
				"fieldtype": "Check",
				"insert_after": "india_payroll_esic_section",
			},
			{
				"fieldname": "esic_registration_number",
				"label": "ESIC Registration Number",
				"fieldtype": "Data",
				"insert_after": "enable_esic",
				"depends_on": "eval:doc.enable_esic",
				"translatable": 0,
			},
		],
		"Employee": [
			{
				"fieldname": "india_payroll_bank_cb",
				"fieldtype": "Column Break",
				"insert_after": "bank_ac_no",
			},
			{
				"fieldname": "ifsc_code",
				"label": "IFSC Code",
				"fieldtype": "Data",
				"insert_after": "india_payroll_bank_cb",
				"print_hide": 1,
				"depends_on": 'eval:doc.salary_mode == "Bank"',
				"translatable": 0,
			},
			{
				"fieldname": "micr_code",
				"label": "MICR Code",
				"fieldtype": "Data",
				"insert_after": "ifsc_code",
				"print_hide": 1,
				"depends_on": 'eval:doc.salary_mode == "Bank"',
				"translatable": 0,
			},
			{
				"fieldname": "payment_mode",
				"label": "Payment Mode",
				"fieldtype": "Select",
				"options": "\nNEFT\nRTGS",
				"insert_after": "micr_code",
				"depends_on": 'eval:doc.salary_mode == "Bank"',
				"translatable": 0,
			},
			{
				"fieldname": "account_type",
				"label": "Account Type",
				"fieldtype": "Select",
				"options": "\nSavings\nCurrent\nSalary",
				"insert_after": "payment_mode",
				"depends_on": 'eval:doc.salary_mode == "Bank"',
				"translatable": 0,
			},
			{
				"fieldname": "india_payroll_esi_section",
				"label": "Employee State Insurance",
				"fieldtype": "Section Break",
				"insert_after": "account_type",
			},
			{
				"fieldname": "esic_card_no",
				"label": "ESIC IP Number",
				"fieldtype": "Data",
				"insert_after": "india_payroll_esi_section",
				"translatable": 0,
				"description": "Employee's ESIC Insurance Number (IP Number) issued by ESIC",
			},
			{
				"fieldname": "is_person_with_disability",
				"label": "Person with Disability",
				"fieldtype": "Check",
				"insert_after": "esic_card_no",
				"description": "ESIC wage ceiling is \u20b925,000 instead of \u20b921,000 for persons with disability",
			},
		],
		"Income Tax Slab": [
			{
				"fieldname": "surcharge_slabs",
				"label": "Surcharge Slabs",
				"fieldtype": "Table",
				"options": "Income Tax Slab Other Charges",
				"insert_after": "taxes_and_charges_on_income_tax_section",
				"reqd": 0,
			},
		],
		"Salary Structure Assignment": [
			{
				"fieldname": "employment_state",
				"label": "Employment State",
				"fieldtype": "Autocomplete",
				"options": "\n".join(INDIA_STATES),
				"insert_after": "employee",
			},
		],
	}


def after_install():
	create_custom_fields(get_custom_fields())
	create_professional_tax_component()
	create_esi_components()
	create_income_tax_slabs()
	setup_tax_exemption_categories()


def after_migrate():
	create_custom_fields(get_custom_fields())


def create_professional_tax_component():
	if frappe.db.exists("Salary Component", "Professional Tax"):
		return

	doc = frappe.new_doc("Salary Component")
	doc.salary_component = "Professional Tax"
	doc.salary_component_abbr = "PT"
	doc.type = "Deduction"
	doc.description = (
		"State-level professional tax levied on salaried employees "
		"under Article 276 of the Indian Constitution (max ₹2,500/year)."
	)
	doc.insert(ignore_permissions=True)


def create_esi_components():
	"""
	Create the Employee State Insurance salary component if it does not
	already exist.

	Only the employee's deduction (0.75 %) is tracked as a salary component.
	The employer's contribution (3.25 %) is part of the CTC and is not shown
	as a separate component on the salary slip.
	"""
	if frappe.db.exists("Salary Component", "Employee State Insurance"):
		return

	doc = frappe.new_doc("Salary Component")
	doc.update(
		{
			"salary_component": "Employee State Insurance",
			"salary_component_abbr": "ESI",
			"type": "Deduction",
			"statistical_component": 0,
			"description": (
				"Employee's contribution to the Employee State Insurance scheme "
				"at 0.75% of gross wages (ESI Act, 1948)."
			),
		}
	)
	doc.insert(ignore_permissions=True)


def create_income_tax_slabs():
	for name, data in INDIA_TAX_SLABS.items():
		if frappe.db.exists("Income Tax Slab", name):
			continue
		doc = frappe.new_doc("Income Tax Slab")
		doc.name = name
		doc.effective_from = data["effective_from"]
		doc.currency = data["currency"]
		doc.allow_tax_exemption = data["allow_tax_exemption"]
		doc.standard_tax_exemption_amount = data["standard_tax_exemption_amount"]
		doc.tax_relief_limit = data["tax_relief_limit"]
		doc.marginal_relief_limit = data["marginal_relief_limit"]

		for row in data["slabs"]:
			doc.append("slabs", row)
		for row in data["surcharge_slabs"]:
			doc.append("surcharge_slabs", row)
		for row in data["other_taxes_and_charges"]:
			doc.append("other_taxes_and_charges", row)

		doc.insert(ignore_permissions=True)
		doc.submit()

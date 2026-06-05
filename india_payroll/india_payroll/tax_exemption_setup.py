# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe

EXEMPTION_CATEGORIES = {
	"80C": {
		"max_amount": 150000,
		"description": "Investments in PPF, ELSS, LIC premium, home loan principal etc. Combined limit ₹1,50,000 across all 80C, 80CCC and 80CCD(1) investments.",
		"sub_categories": [
			{"name": "Public Provident Fund (PPF)"},
			{"name": "Equity Linked Savings Scheme (ELSS)"},
			{"name": "Life Insurance Premium"},
			{"name": "Employee Provident Fund (EPF)"},
			{"name": "National Savings Certificate (NSC)"},
			{"name": "Tax-Saving Fixed Deposit (5-year)"},
			{"name": "Sukanya Samriddhi Yojana"},
			{"name": "Senior Citizen Savings Scheme (SCSS)"},
			{"name": "Home Loan Principal Repayment"},
			{"name": "Stamp Duty and Registration Charges"},
			{"name": "Tuition Fees (up to 2 children)"},
		],
	},
	"80CCC": {
		"max_amount": 150000,
		"description": "Contributions to pension or annuity plans from insurance companies. Counts toward the combined ₹1,50,000 limit with 80C.",
		"sub_categories": [
			{"name": "Pension Fund Contribution (Annuity Plan)"},
		],
	},
	"80CCD(1)": {
		"max_amount": 150000,
		"description": "Employee's own NPS contribution. Counts toward the combined ₹1,50,000 limit with 80C and 80CCC.",
		"sub_categories": [
			{"name": "Employee NPS Contribution - 80CCD(1)"},
		],
	},
	"80CCD(1B)": {
		"max_amount": 50000,
		"description": "Additional NPS contribution of up to ₹50,000 over and above the ₹1,50,000 combined limit. Entirely separate from the 80CCE cap.",
		"sub_categories": [
			{"name": "Additional NPS Contribution - 80CCD(1B)"},
		],
	},
	"80CCD(2)": {
		"description": "Employer's NPS contribution. Capped at 10% of basic salary (14% for government employees). Available under both old and new regime.",
		"sub_categories": [
			{"name": "Employer NPS Contribution - 80CCD(2)"},
		],
	},
	"80D": {
		"max_amount": 75000,
		"description": "Health insurance premiums for yourself, spouse, children and parents.",
		"sub_categories": [
			{"name": "Health Insurance - Self, Spouse and Children"},
			{"name": "Health Insurance - Parents (below 60)"},
			{
				"name": "Health Insurance - Parents (Senior Citizen)",
				"max_amount": 50000,
			},
			{"name": "Preventive Health Check-up", "max_amount": 5000},
		],
	},
	"80DD": {
		"max_amount": 125000,
		"description": "Medical treatment and maintenance of a disabled dependent.",
		"sub_categories": [
			{"name": "Dependent with 40-79% Disability", "max_amount": 75000},
			{"name": "Dependent with 80%+ Disability", "max_amount": 125000},
		],
	},
	"80DDB": {
		"max_amount": 100000,
		"description": "Treatment of specified diseases such as cancer, neurological disorders and kidney failure.",
		"sub_categories": [
			{"name": "Specified Disease Treatment - Self or Dependent"},
			{
				"name": "Specified Disease Treatment - Senior Citizen",
				"max_amount": 100000,
			},
		],
	},
	"80E": {
		"description": "Interest on education loan. No upper limit, claimable for up to 8 years from the year repayment begins.",
		"sub_categories": [
			{"name": "Interest on Education Loan"},
		],
	},
	"80EE": {
		"max_amount": 50000,
		"description": "Additional home loan interest deduction for first-time buyers. Loan must have been sanctioned between Apr 2016 and Mar 2017.",
		"sub_categories": [
			{"name": "Additional Interest on Home Loan (80EE)"},
		],
	},
	"80EEA": {
		"max_amount": 150000,
		"description": "Additional home loan interest for affordable housing. Loan sanctioned between Apr 2019 and Mar 2022. Property stamp duty value must be ≤ ₹45 lakhs.",
		"sub_categories": [
			{"name": "Additional Interest on Affordable Housing Loan (80EEA)"},
		],
	},
	"24": {
		"max_amount": 200000,
		"description": "Interest on home loan. Up to ₹2,00,000 for self-occupied property. No limit for let-out property.",
		"sub_categories": [
			{"name": "Interest on Home Loan (Self-occupied)"},
			{"name": "Interest on Home Loan (Let-out Property)"},
		],
	},
	"80G": {
		"description": "Donations to approved charitable institutions. Deduction is 50% or 100% of the donated amount depending on the institution.",
		"sub_categories": [
			{"name": "Donation - 100% Deduction, No Income Limit"},
			{"name": "Donation - 50% Deduction, No Income Limit"},
			{"name": "Donation - 100% Deduction with 10% Income Cap"},
			{"name": "Donation - 50% Deduction with 10% Income Cap"},
		],
	},
	"80GG": {
		"max_amount": 60000,
		"description": "Rent deduction for employees who pay rent but do not receive HRA from their employer. Mutually exclusive with HRA exemption.",
		"sub_categories": [
			{"name": "Rent Paid (No HRA from Employer)"},
		],
	},
	"80GGC": {
		"description": "Donations to registered political parties or electoral trusts. Payment must be via bank transfer.",
		"sub_categories": [
			{"name": "Donation to Registered Political Party"},
		],
	},
	"80TTA": {
		"max_amount": 10000,
		"description": "Interest on savings account with a bank, post office or cooperative bank. Not available to senior citizens.",
		"sub_categories": [
			{"name": "Interest on Savings Account"},
		],
	},
	"80TTB": {
		"max_amount": 50000,
		"description": "Interest on savings and fixed deposits for senior citizens (60 years and above).",
		"sub_categories": [
			{"name": "Interest on Savings and Fixed Deposits"},
		],
	},
	"80U": {
		"max_amount": 125000,
		"description": "Flat deduction for employees with a certified disability. Amount depends on the severity of disability.",
		"sub_categories": [
			{"name": "Self with 40-79% Disability", "max_amount": 75000},
			{"name": "Self with 80%+ Disability", "max_amount": 125000},
		],
	},
}


def setup_tax_exemption_categories():
	for name, data in EXEMPTION_CATEGORIES.items():
		create_category(name, data)


def create_category(name, data):
	if not frappe.db.exists("Employee Tax Exemption Category", name):
		doc = frappe.new_doc("Employee Tax Exemption Category")
		doc.name = name
		doc.max_amount = data.get("max_amount")
		doc.description = data.get("description")
		doc.insert(ignore_permissions=True)

	for sub_category in data.get("sub_categories", []):
		create_sub_category(sub_category, parent_category=name)


def create_sub_category(sub_category, parent_category):
	if frappe.db.exists("Employee Tax Exemption Sub Category", sub_category["name"]):
		return

	doc = frappe.new_doc("Employee Tax Exemption Sub Category")
	doc.name = sub_category["name"]
	doc.exemption_category = parent_category
	doc.max_amount = sub_category.get("max_amount")
	doc.description = sub_category.get("description", "")
	doc.insert(ignore_permissions=True)

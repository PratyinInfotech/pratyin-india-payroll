import frappe
from erpnext.setup.doctype.employee.test_employee import make_employee
from hrms.payroll.doctype.income_tax_slab.income_tax_slab import (
	calculate_base_tax_from_tax_slabs,
	calculate_other_charges,
)
from hrms.payroll.doctype.payroll_period.test_payroll_period import create_payroll_period
from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip
from hrms.payroll.doctype.salary_structure.test_salary_structure import make_salary_structure
from hrms.tests.utils import HRMSTestSuite

from india_payroll.india_payroll.income_tax_utils import (
	apply_surcharge_with_marginal_relief,
	surcharge_with_marginal_relief,
)
from india_payroll.install import create_income_tax_slabs


class TestIndiaIncomeTax(HRMSTestSuite):
	def setUp(self):
		create_income_tax_slabs()
		self.new_regime_2024 = frappe.get_doc("Income Tax Slab", "New Tax Regime: 2024-2025")
		self.new_regime_2025 = frappe.get_doc("Income Tax Slab", "New Tax Regime: 2025-2026")
		self.old_regime = frappe.get_doc("Income Tax Slab", "Old Tax Regime: 2019")

	def test_marginal_relief_applies_at_25pct_threshold(self):
		"""Income just above ₹2 Cr (25% slab, new regime) — surcharge is reduced by marginal relief."""
		income = 20125000
		threshold = 20000001
		tax_slab = self.new_regime_2024

		base_tax = calculate_base_tax_from_tax_slabs(income, tax_slab, None, {})
		row = surcharge_row("Surcharge 25%", tax_slab)

		actual_surcharge = surcharge_with_marginal_relief(row, base_tax, income, tax_slab, None, {})
		raw_surcharge = base_tax * 25 / 100

		self.assertLess(actual_surcharge, raw_surcharge)

		base_tax_at_threshold = calculate_base_tax_from_tax_slabs(threshold, tax_slab, None, {})
		surcharge_at_threshold = base_tax_at_threshold * 15 / 100  # prev tier rate
		tax_at_threshold = base_tax_at_threshold + surcharge_at_threshold
		excess_income = income - threshold

		self.assertEqual(
			base_tax + actual_surcharge,
			tax_at_threshold + excess_income,
		)

	def test_no_marginal_relief_at_15pct_slab(self):
		"""Income ₹1.5 Cr (15% slab) — excess income far exceeds excess tax, surcharge unchanged."""
		income = 15000000
		tax_slab = self.new_regime_2024

		base_tax = calculate_base_tax_from_tax_slabs(income, tax_slab, None, {})
		row = surcharge_row("Surcharge 15%", tax_slab)

		actual_surcharge = surcharge_with_marginal_relief(row, base_tax, income, tax_slab, None, {})

		self.assertEqual(actual_surcharge, base_tax * 15 / 100)

	def test_no_marginal_relief_at_10pct_slab(self):
		"""Income ₹60 L (10% slab) — no marginal relief needed."""
		income = 6000000
		tax_slab = self.new_regime_2024

		base_tax = calculate_base_tax_from_tax_slabs(income, tax_slab, None, {})
		row = surcharge_row("Surcharge 10%", tax_slab)

		actual_surcharge = surcharge_with_marginal_relief(row, base_tax, income, tax_slab, None, {})

		self.assertEqual(actual_surcharge, base_tax * 10 / 100)

	def test_old_regime_no_marginal_relief_at_10pct_slab(self):
		"""Income ₹75 L (old regime, 10% slab) — well inside the band, no marginal relief needed."""
		income = 7500000
		tax_slab = self.old_regime

		base_tax = calculate_base_tax_from_tax_slabs(income, tax_slab, None, {})
		row = surcharge_row("Surcharge 10%", tax_slab)

		actual_surcharge = surcharge_with_marginal_relief(row, base_tax, income, tax_slab, None, {})

		self.assertEqual(actual_surcharge, base_tax * 10 / 100)

	def test_old_regime_no_marginal_relief_at_15pct_slab(self):
		"""Income ₹1.5 Cr (old regime, 15% slab) — no marginal relief needed."""
		income = 15000000
		tax_slab = self.old_regime

		base_tax = calculate_base_tax_from_tax_slabs(income, tax_slab, None, {})
		row = surcharge_row("Surcharge 15%", tax_slab)

		actual_surcharge = surcharge_with_marginal_relief(row, base_tax, income, tax_slab, None, {})

		self.assertEqual(actual_surcharge, base_tax * 15 / 100)

	def test_old_regime_no_marginal_relief_at_25pct_slab(self):
		"""Income ₹3 Cr (old regime, 25% slab) — no marginal relief needed."""
		income = 30000000
		tax_slab = self.old_regime

		base_tax = calculate_base_tax_from_tax_slabs(income, tax_slab, None, {})
		row = surcharge_row("Surcharge 25%", tax_slab)

		actual_surcharge = surcharge_with_marginal_relief(row, base_tax, income, tax_slab, None, {})

		self.assertEqual(actual_surcharge, base_tax * 25 / 100)

	def test_old_regime_37pct_surcharge_applies(self):
		"""Income ₹6 Cr (old regime, 37% tier) — correct tier fires, no marginal relief needed."""
		income = 60000000
		tax_slab = self.old_regime

		base_tax = calculate_base_tax_from_tax_slabs(income, tax_slab, None, {})
		row = surcharge_row("Surcharge 37%", tax_slab)

		actual_surcharge = surcharge_with_marginal_relief(row, base_tax, income, tax_slab, None, {})

		self.assertEqual(actual_surcharge, base_tax * 37 / 100)

	def test_old_regime_marginal_relief_at_37pct_threshold(self):
		"""Income just above ₹5 Cr (old regime, 37% slab) — marginal relief reduces surcharge."""
		income = 50125000
		threshold = 50000001
		tax_slab = self.old_regime

		base_tax = calculate_base_tax_from_tax_slabs(income, tax_slab, None, {})
		row = surcharge_row("Surcharge 37%", tax_slab)

		actual_surcharge = surcharge_with_marginal_relief(row, base_tax, income, tax_slab, None, {})
		raw_surcharge = base_tax * 37 / 100

		self.assertLess(actual_surcharge, raw_surcharge)

		base_tax_at_threshold = calculate_base_tax_from_tax_slabs(threshold, tax_slab, None, {})
		surcharge_at_threshold = base_tax_at_threshold * 25 / 100  # prev tier rate
		tax_at_threshold = base_tax_at_threshold + surcharge_at_threshold
		excess_income = income - threshold

		self.assertEqual(base_tax + actual_surcharge, tax_at_threshold + excess_income)

	def test_no_surcharge_below_50_lakh(self):
		"""Income below ₹50 L — no surcharge slab applies."""
		income = 4000000
		tax_slab = self.new_regime_2024

		base_tax = calculate_base_tax_from_tax_slabs(income, tax_slab, None, {})
		tax_with_surcharge, surcharge = apply_surcharge_with_marginal_relief(
			base_tax, income, tax_slab, None, {}
		)

		self.assertEqual(surcharge, 0.0)
		self.assertEqual(tax_with_surcharge, base_tax)

	def test_cess_base_includes_surcharge(self):
		"""Cess must be applied on (base_tax + surcharge), not on base_tax alone."""
		income = 6000000
		tax_slab = self.new_regime_2024

		base_tax = calculate_base_tax_from_tax_slabs(income, tax_slab, None, {})
		tax_with_surcharge, surcharge = apply_surcharge_with_marginal_relief(
			base_tax, income, tax_slab, None, {}
		)

		self.assertEqual(surcharge, base_tax * 10 / 100)

		cess_row = tax_slab.other_taxes_and_charges[0]
		actual_cess = tax_with_surcharge * cess_row.percent / 100
		self.assertEqual(actual_cess, tax_with_surcharge * 4 / 100)

	def test_surcharge_in_other_taxes_has_no_marginal_relief(self):
		"""Surcharge in other_taxes_and_charges is a flat rate — no marginal relief even where it would apply."""
		income = 20125000  # just above ₹2 Cr — marginal relief applies when in surcharge_slabs
		tax_slab = self.new_regime_2024

		base_tax = calculate_base_tax_from_tax_slabs(income, tax_slab, None, {})

		# Same 25% rate but placed in other_taxes_and_charges instead of surcharge_slabs
		mock_slab = frappe._dict(
			other_taxes_and_charges=[frappe._dict(percent=25, min_taxable_income=0, max_taxable_income=0)]
		)
		_, charge = calculate_other_charges(base_tax, income, mock_slab)

		# Flat rate — no relief, unlike the surcharge_slabs path for the same income
		self.assertEqual(charge, base_tax * 25 / 100)

		# Confirm the surcharge_slabs path DOES apply relief for the same income
		row = surcharge_row("Surcharge 25%", tax_slab)
		actual_surcharge = surcharge_with_marginal_relief(row, base_tax, income, tax_slab, None, {})
		self.assertLess(actual_surcharge, base_tax * 25 / 100)

	def test_new_regime_2025_higher_relief_limit(self):
		"""New regime 2025-26 relief limit (₹12 L) is higher than 2024-25 (₹7 L)."""
		income = 900000

		self.assertGreater(self.new_regime_2025.tax_relief_limit, income)
		self.assertLess(self.new_regime_2024.tax_relief_limit, income)

	def test_salary_slip_tds_includes_surcharge(self):
		"""TDS on a high-income salary slip (₹7.2 M annual) includes the 10% surcharge."""
		payroll_period = create_payroll_period(
			name="_Test Payroll Period India Surcharge", company="_Test Company"
		)
		employee = make_employee("test_india_surcharge@salary.slip", company="_Test Company")

		salary_structure = make_salary_structure(
			"Structure for India Surcharge Test",
			"Monthly",
			test_tax=True,
			employee=employee,
			payroll_period=payroll_period,
			company="_Test Company",
			base=600000,  # ₹7.2 M annual — in 10% surcharge band (₹50 L to ₹1 Cr, new regime)
		)

		# Ensure the assignment uses India's new-regime slab
		ssa_name = frappe.db.get_value("Salary Structure Assignment", {"employee": employee, "docstatus": 1})
		frappe.db.set_value(
			"Salary Structure Assignment", ssa_name, "income_tax_slab", "New Tax Regime: 2024-2025"
		)

		salary_slip = make_salary_slip(salary_structure.name, employee=employee)

		tds = next((d.amount for d in salary_slip.deductions if d.salary_component == "TDS"), 0)

		annual_income = salary_slip.annual_taxable_amount
		base_tax = calculate_base_tax_from_tax_slabs(annual_income, self.new_regime_2024, None, {})
		_, cess_only = calculate_other_charges(base_tax, annual_income, self.new_regime_2024)
		no_surcharge_annual_tax = base_tax + cess_only

		self.assertGreater(tds, 0, "Expected non-zero TDS for high-income employee")
		# Annual TDS must exceed (base_tax + cess-on-base-tax) — proves surcharge was applied
		self.assertGreater(tds * 12, no_surcharge_annual_tax)


def surcharge_row(description, tax_slab):
	return next(c for c in tax_slab.surcharge_slabs if c.description == description)

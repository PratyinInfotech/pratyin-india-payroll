# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from erpnext.setup.doctype.employee.test_employee import make_employee
from frappe.utils import flt
from hrms.payroll.doctype.salary_slip.test_salary_slip import make_salary_component
from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip
from hrms.payroll.doctype.salary_structure.test_salary_structure import (
	create_salary_structure_assignment,
	make_salary_structure,
)
from hrms.tests.utils import HRMSTestSuite

from india_payroll.india_payroll.epf import (
	EDLI_COMPONENT,
	EMPLOYER_EPF_COMPONENT,
	EMPLOYER_EPS_COMPONENT,
	EPF_ADMIN_COMPONENT,
	EPF_EMPLOYEE_COMPONENT,
	EPF_WAGE_CEILING,
	VPF_COMPONENT,
)
from india_payroll.install import create_epf_components

# A PF-eligible earning component used as Basic across all EPF tests.
# `include_in_pf_wage` is flagged so the rule engine picks it up; formula
# `base` keeps gross_pay equal to the SSA base for predictable assertions.
_EPF_BASIC_COMPONENT = "EPF Test Basic"
_EPF_TEST_EARNINGS = [
	{
		"salary_component": _EPF_BASIC_COMPONENT,
		"abbr": "EPFTB",
		"formula": "base",
		"type": "Earning",
		"amount_based_on_formula": 1,
		"depends_on_payment_days": 0,
	}
]

_TEST_EMAILS = [
	"test_epf_below_ceiling@indiapayroll.com",
	"test_epf_above_ceiling_capped@indiapayroll.com",
	"test_epf_above_ceiling_actual@indiapayroll.com",
	"test_epf_high_earner_no_eps@indiapayroll.com",
	"test_epf_at_ceiling_eps_applies@indiapayroll.com",
	"test_epf_vpf@indiapayroll.com",
	"test_epf_not_applicable@indiapayroll.com",
	"test_epf_disabled_setting@indiapayroll.com",
	"test_epf_net_pay@indiapayroll.com",
	"test_epf_rounding@indiapayroll.com",
]


class TestEPF(HRMSTestSuite):
	def setUp(self):
		create_epf_components()
		self._ensure_epf_test_component()
		self._cleanup()

	def _ensure_epf_test_component(self):
		"""
		Create the EPF-specific basic component if absent and ensure it's
		flagged include_in_pf_wage so the rule engine treats it as PF wage.
		"""
		if not frappe.db.exists("Salary Component", _EPF_BASIC_COMPONENT):
			make_salary_component(_EPF_TEST_EARNINGS, False, ["_Test Company"])
		frappe.db.set_value("Salary Component", _EPF_BASIC_COMPONENT, "include_in_pf_wage", 1)

	def _cleanup(self):
		for email in _TEST_EMAILS:
			frappe.db.delete("Salary Slip", {"employee_name": email})
			emp = frappe.db.get_value("Employee", {"employee_name": email}, "name")
			if emp:
				frappe.db.delete("Salary Structure Assignment", {"employee": emp})

	def _make_salary_slip(
		self,
		email: str,
		structure_name: str,
		gross_pay: float,
		*,
		epf_applicable: bool = True,
		posting_date: str = "2026-04-01",
		start_date: str = "2026-04-01",
		end_date: str = "2026-04-30",
	):
		"""
		Create a salary slip whose Basic (PF-eligible) equals `gross_pay`.

		Sets Employee.epf_applicable so the hook treats the employee as
		opted into EPF deduction.
		"""
		employee = make_employee(email, company="_Test Company")
		frappe.db.set_value("Employee", employee, "epf_applicable", 1 if epf_applicable else 0)

		salary_structure = make_salary_structure(
			structure_name,
			"Monthly",
			company="_Test Company",
			currency="INR",
			earnings=_EPF_TEST_EARNINGS,
			deductions=[],
		)

		create_salary_structure_assignment(
			employee,
			salary_structure.name,
			from_date=start_date,
			company="_Test Company",
			base=gross_pay,
		)

		salary_slip = make_salary_slip(
			salary_structure.name,
			employee=employee,
			posting_date=posting_date,
		)
		salary_slip.start_date = start_date
		salary_slip.end_date = end_date

		return employee, salary_slip

	@staticmethod
	def _amount(slip, table: str, component: str) -> float:
		row = next(
			(r for r in getattr(slip, table) if r.salary_component == component),
			None,
		)
		return flt(row.amount) if row else 0.0

	@HRMSTestSuite.change_settings(
		"Payroll Settings",
		{"enable_epf": 1, "enable_professional_tax": 0, "enable_esic": 0, "enable_lwf": 0},
	)
	def test_at_ceiling_standard_12_percent(self):
		"""
		PF wage ₹15,000 (= ceiling) should deduct ₹1,800 (12%).
		Employer split: EPS = ₹1,250 (8.33% * 15,000, half-up), Employer EPF = ₹550.
		EDLI = ₹75, EPF Admin = ₹75.
		"""
		gross = float(EPF_WAGE_CEILING)
		_, slip = self._make_salary_slip(
			"test_epf_below_ceiling@indiapayroll.com",
			"Test EPF At Ceiling Structure",
			gross,
		)
		slip.insert()

		self.assertEqual(self._amount(slip, "deductions", EPF_EMPLOYEE_COMPONENT), 1_800)
		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPS_COMPONENT), 1_250)
		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPF_COMPONENT), 550)
		self.assertEqual(self._amount(slip, "earnings", EDLI_COMPONENT), 75)
		self.assertEqual(self._amount(slip, "earnings", EPF_ADMIN_COMPONENT), 75)

	@HRMSTestSuite.change_settings(
		"Payroll Settings",
		{"enable_epf": 1, "enable_professional_tax": 0, "enable_esic": 0, "enable_lwf": 0},
	)
	def test_above_ceiling_default_caps_at_15000(self):
		"""
		PF wage ₹25,000 with `contribute_on_actual_pf_wage` unset (default).
		Employee + employer EPF capped at ₹15,000 → ₹1,800 each side.
		But because PF wage > ₹15,000 the post-2014 rule applies — EPS = 0
		and the full employer ₹1,800 goes to Employer EPF.
		"""
		gross = 25_000.0
		_, slip = self._make_salary_slip(
			"test_epf_above_ceiling_capped@indiapayroll.com",
			"Test EPF Above Ceiling Capped Structure",
			gross,
		)
		slip.insert()

		self.assertEqual(self._amount(slip, "deductions", EPF_EMPLOYEE_COMPONENT), 1_800)
		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPS_COMPONENT), 0)
		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPF_COMPONENT), 1_800)

	@HRMSTestSuite.change_settings(
		"Payroll Settings",
		{"enable_epf": 1, "enable_professional_tax": 0, "enable_esic": 0, "enable_lwf": 0},
	)
	def test_above_ceiling_contribute_on_actual(self):
		"""
		PF wage ₹25,000 with `contribute_on_actual_pf_wage = 1`.
		  Employee EPF: 12% * 25,000 = ₹3,000
		  Employer total: 12% * 25,000 = ₹3,000 (all to EPF — no EPS for high earners)
		  EDLI: 0.5% * 15,000 = ₹75 (always capped by law)
		"""
		gross = 25_000.0
		employee, slip = self._make_salary_slip(
			"test_epf_above_ceiling_actual@indiapayroll.com",
			"Test EPF Above Ceiling Actual Structure",
			gross,
		)
		frappe.db.set_value("Employee", employee, "contribute_on_actual_pf_wage", 1)
		slip.insert()

		self.assertEqual(self._amount(slip, "deductions", EPF_EMPLOYEE_COMPONENT), 3_000)
		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPS_COMPONENT), 0)
		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPF_COMPONENT), 3_000)
		self.assertEqual(self._amount(slip, "earnings", EDLI_COMPONENT), 75)

	@HRMSTestSuite.change_settings(
		"Payroll Settings",
		{"enable_epf": 1, "enable_professional_tax": 0, "enable_esic": 0, "enable_lwf": 0},
	)
	def test_just_above_ceiling_no_eps(self):
		"""
		Even ₹1 above the ceiling triggers the EPS-ineligibility rule.
		At PF wage ₹15,001:
		  • capped contributions: 12% * 15,000 = ₹1,800 each side
		  • EPS = 0, Employer EPF = ₹1,800
		"""
		gross = float(EPF_WAGE_CEILING + 1)
		_, slip = self._make_salary_slip(
			"test_epf_high_earner_no_eps@indiapayroll.com",
			"Test EPF Just Above Ceiling Structure",
			gross,
		)
		slip.insert()

		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPS_COMPONENT), 0)
		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPF_COMPONENT), 1_800)

	@HRMSTestSuite.change_settings(
		"Payroll Settings",
		{"enable_epf": 1, "enable_professional_tax": 0, "enable_esic": 0, "enable_lwf": 0},
	)
	def test_at_ceiling_eps_applies(self):
		"""
		At exactly ₹15,000 the EPS rule still applies (cutoff is strictly >).
		"""
		gross = float(EPF_WAGE_CEILING)
		_, slip = self._make_salary_slip(
			"test_epf_at_ceiling_eps_applies@indiapayroll.com",
			"Test EPF At Ceiling EPS Applies Structure",
			gross,
		)
		slip.insert()

		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPS_COMPONENT), 1_250)
		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPF_COMPONENT), 550)

	@HRMSTestSuite.change_settings(
		"Payroll Settings",
		{"enable_epf": 1, "enable_professional_tax": 0, "enable_esic": 0, "enable_lwf": 0},
	)
	def test_vpf_adds_separate_deduction_row(self):
		"""
		An employee with vpf_percentage = 5 contributes 5% extra on top of 12%.
		Employee EPF: 12% * 15,000 = ₹1,800
		VPF:          5% * 15,000 = ₹750
		Employer side is unchanged — no matching contribution for VPF.
		"""
		gross = float(EPF_WAGE_CEILING)
		employee, slip = self._make_salary_slip(
			"test_epf_vpf@indiapayroll.com",
			"Test EPF VPF Structure",
			gross,
		)
		frappe.db.set_value("Employee", employee, "vpf_percentage", 5)
		slip.insert()

		self.assertEqual(self._amount(slip, "deductions", EPF_EMPLOYEE_COMPONENT), 1_800)
		self.assertEqual(self._amount(slip, "deductions", VPF_COMPONENT), 750)
		# Employer EPS still 8.33% * 15k = 1250 — VPF doesn't move it
		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPS_COMPONENT), 1_250)

	@HRMSTestSuite.change_settings(
		"Payroll Settings",
		{"enable_epf": 1, "enable_professional_tax": 0, "enable_esic": 0, "enable_lwf": 0},
	)
	def test_not_applicable_no_epf_rows(self):
		"""
		Employee.epf_applicable = 0 must suppress every EPF-scheme row, even
		when EPF is enabled in Payroll Settings.
		"""
		_, slip = self._make_salary_slip(
			"test_epf_not_applicable@indiapayroll.com",
			"Test EPF Not Applicable Structure",
			15_000.0,
			epf_applicable=False,
		)
		slip.insert()

		self.assertEqual(self._amount(slip, "deductions", EPF_EMPLOYEE_COMPONENT), 0)
		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPF_COMPONENT), 0)
		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPS_COMPONENT), 0)

	@HRMSTestSuite.change_settings(
		"Payroll Settings",
		{"enable_epf": 0, "enable_professional_tax": 0, "enable_esic": 0, "enable_lwf": 0},
	)
	def test_disabled_setting_no_epf_rows(self):
		"""
		Master switch off → no EPF rows even if Employee.epf_applicable is on.
		"""
		_, slip = self._make_salary_slip(
			"test_epf_disabled_setting@indiapayroll.com",
			"Test EPF Disabled Setting Structure",
			15_000.0,
		)
		slip.insert()

		self.assertEqual(self._amount(slip, "deductions", EPF_EMPLOYEE_COMPONENT), 0)
		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPF_COMPONENT), 0)

	@HRMSTestSuite.change_settings(
		"Payroll Settings",
		{"enable_epf": 1, "enable_professional_tax": 0, "enable_esic": 0, "enable_lwf": 0},
	)
	def test_net_pay_reduced_only_by_employee_share(self):
		"""
		Net pay must drop only by Employee PF + VPF; employer contributions
		are statistical and must NOT shift net pay or gross.
		"""
		gross = float(EPF_WAGE_CEILING)
		employee, slip = self._make_salary_slip(
			"test_epf_net_pay@indiapayroll.com",
			"Test EPF Net Pay Structure",
			gross,
		)
		frappe.db.set_value("Employee", employee, "vpf_percentage", 5)
		slip.insert()

		expected_deduction = 1_800 + 750  # employee 12% + VPF 5%
		self.assertAlmostEqual(slip.total_deduction, expected_deduction, places=2)
		self.assertAlmostEqual(slip.gross_pay, gross, places=2)
		self.assertAlmostEqual(slip.net_pay, gross - expected_deduction, places=2)

	@HRMSTestSuite.change_settings(
		"Payroll Settings",
		{"enable_epf": 1, "enable_professional_tax": 0, "enable_esic": 0, "enable_lwf": 0},
	)
	def test_eps_half_up_rounding(self):
		"""
		8.33% * 15,000 = 1249.5 must round HALF-UP to ₹1,250, per EPFO
		convention.  Python's built-in round() uses banker's rounding which
		can give different results at .5 boundaries; we use explicit half-up.
		"""
		gross = float(EPF_WAGE_CEILING)
		_, slip = self._make_salary_slip(
			"test_epf_rounding@indiapayroll.com",
			"Test EPF Rounding Structure",
			gross,
		)
		slip.insert()

		self.assertEqual(self._amount(slip, "earnings", EMPLOYER_EPS_COMPONENT), 1_250)

# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import flt

# Employee deductions (reduce net pay).  Employer EPF/EPS/EDLI/Admin are
# components of type "Employer Contribution" and live on the Salary Structure's
# employer_contributions table — they're rolled into CTC by Salary Structure
# Assignment and are not injected onto the slip.
EPF_EMPLOYEE_COMPONENT = "Provident Fund"
VPF_COMPONENT = "Voluntary Provident Fund"

EPF_EMPLOYEE_COMPONENTS = (EPF_EMPLOYEE_COMPONENT, VPF_COMPONENT)

# --- Statutory constants --------------------------------------------------
EPF_WAGE_CEILING = 15_000  # PF / EPS / EDLI statutory ceiling
EPF_EMPLOYEE_RATE = 0.12  # employee EPF share


def apply_epf(doc, method=None) -> None:
	"""
	Salary Slip — before_save hook.

	Computes and injects employee EPF-scheme rows on the slip:
	  • Employee contribution (12 %)   → deductions
	  • VPF top-up (optional)          → deductions

	Employer contributions (EPF / EPS / EDLI / Admin) are configured as
	"Employer Contribution" components on the Salary Structure and handled
	by Salary Structure Assignment / CTC — not by this hook.

	Gated by a single `epf_applicable` flag on the Employee master.  All
	employees are assumed to be post-1 Sept 2014 EPF members.
	"""
	if not frappe.db.get_single_value("Payroll Settings", "enable_epf"):
		_remove_epf_components(doc)
		return

	if not doc.salary_structure:
		return

	if not _is_epf_applicable(doc.employee):
		_remove_epf_components(doc)
		return

	if not _required_components_exist():
		frappe.msgprint(
			frappe._(
				"One or more EPF Salary Components are missing. "
				"Please reinstall the India Payroll app or create them manually."
			),
			indicator="orange",
			alert=True,
		)
		return

	pf_wage = _compute_pf_wage(doc)
	if pf_wage <= 0:
		# Nothing to contribute on (e.g. no components flagged as PF wage)
		_remove_epf_components(doc)
		return

	contribute_on_actual = bool(frappe.db.get_value("Employee", doc.employee, "contribute_on_actual_pf_wage"))
	pf_wage_capped = min(pf_wage, EPF_WAGE_CEILING)
	epf_base = pf_wage if contribute_on_actual else pf_wage_capped

	employee_epf = _epfo_round(epf_base * EPF_EMPLOYEE_RATE)
	vpf = _compute_vpf(doc.employee, epf_base)

	_apply_epf_components(doc, employee_epf=employee_epf, vpf=vpf)
	_recalculate_totals(doc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_epf_applicable(employee: str) -> bool:
	"""Return True if EPF is opted-in on the Employee master."""
	return bool(frappe.db.get_value("Employee", employee, "epf_applicable"))


def _required_components_exist() -> bool:
	"""Both employee-side EPF salary components must exist before we inject rows."""
	for name in EPF_EMPLOYEE_COMPONENTS:
		if not frappe.db.exists("Salary Component", name):
			return False
	return True


def _compute_pf_wage(doc) -> float:
	"""
	Sum earnings amounts for components flagged `include_in_pf_wage`.

	The 2019 Supreme Court ruling broadened PF wages beyond Basic + DA to
	include any allowance universally and ordinarily paid.  Which components
	qualify is a definitional landmine, so we let companies tick the flag on
	each Salary Component rather than hard-coding the list.

	Amounts on `doc.earnings` are already prorated for LOP / payment_days by
	the Salary Slip controller, so the returned PF wage reflects NCP days.
	"""
	pf_components = set(
		frappe.get_all(
			"Salary Component",
			filters={"include_in_pf_wage": 1},
			pluck="name",
		)
	)
	if not pf_components:
		return 0.0
	return sum(flt(e.amount) for e in doc.earnings if e.salary_component in pf_components)


def _compute_vpf(employee: str, epf_base: float) -> float:
	"""
	Voluntary Provident Fund — additional employee contribution above 12 %.

	Configured as a percentage on the Employee master.  The employer does
	not match VPF.
	"""
	vpf_pct = flt(frappe.db.get_value("Employee", employee, "vpf_percentage"))
	if vpf_pct <= 0:
		return 0.0
	return _epfo_round(epf_base * vpf_pct / 100.0)


def _apply_epf_components(doc, *, employee_epf: float, vpf: float) -> None:
	"""Replace any existing employee EPF rows on the slip with fresh amounts."""
	doc.deductions = [d for d in doc.deductions if d.salary_component not in EPF_EMPLOYEE_COMPONENTS]

	if employee_epf > 0:
		doc.append(
			"deductions",
			{"salary_component": EPF_EMPLOYEE_COMPONENT, "amount": employee_epf},
		)

	if vpf > 0:
		doc.append(
			"deductions",
			{"salary_component": VPF_COMPONENT, "amount": vpf},
		)


def _remove_epf_components(doc) -> None:
	"""Strip employee EPF rows from deductions; recalculate."""
	before = len(doc.deductions)
	doc.deductions = [d for d in doc.deductions if d.salary_component not in EPF_EMPLOYEE_COMPONENTS]
	if len(doc.deductions) != before:
		_recalculate_totals(doc)


def _recalculate_totals(doc) -> None:
	"""Recompute total_deduction and net_pay after modifying deduction rows."""
	doc.total_deduction = sum(flt(d.amount) for d in doc.deductions if not d.do_not_include_in_total)
	doc.net_pay = flt(doc.gross_pay) - flt(doc.total_deduction)
	if hasattr(doc, "rounded_total"):
		doc.rounded_total = round(doc.net_pay)


def _epfo_round(amount: float) -> int:
	"""
	Round to the nearest rupee per EPFO conventions (half-up).

	Python's built-in `round()` uses banker's rounding, which can give
	surprising results at .5 boundaries (e.g. EPS = 8.33 % * 15,000 = 1249.5
	must become ₹1,250, not ₹1,249).  We use explicit half-up here.
	"""
	a = flt(amount)
	if a >= 0:
		return int(a + 0.5)
	return -int(-a + 0.5)

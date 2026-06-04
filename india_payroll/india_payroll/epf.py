# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import flt

# --- Salary components ----------------------------------------------------
# Employee deductions (reduce net pay)
EPF_EMPLOYEE_COMPONENT = "Provident Fund"
VPF_COMPONENT = "Voluntary Provident Fund"

# Employer contributions (statistical — computed, reportable, but excluded
# from total_deduction / net_pay).  Employer cost is part of the CTC.
EMPLOYER_EPF_COMPONENT = "Employer Provident Fund"
EMPLOYER_EPS_COMPONENT = "Employer Pension Scheme"
EDLI_COMPONENT = "Employees Deposit Linked Insurance"
EPF_ADMIN_COMPONENT = "EPF Admin Charges"

EPF_ALL_COMPONENTS = (
	EPF_EMPLOYEE_COMPONENT,
	VPF_COMPONENT,
	EMPLOYER_EPF_COMPONENT,
	EMPLOYER_EPS_COMPONENT,
	EDLI_COMPONENT,
	EPF_ADMIN_COMPONENT,
)

# --- Statutory constants --------------------------------------------------
EPF_WAGE_CEILING = 15_000  # PF / EPS / EDLI statutory ceiling

EPF_EMPLOYEE_RATE = 0.12  # employee EPF share
EPF_EMPLOYER_RATE = 0.12  # employer total share (split between EPF + EPS)
EPS_RATE = 0.0833  # employer's pension diversion
EDLI_RATE = 0.005  # employer's EDLI premium
EPF_ADMIN_RATE = 0.005  # employer's EPF admin charges


def apply_epf(doc, method=None) -> None:
	"""
	Salary Slip — before_save hook.

	Computes and injects EPF-scheme rows:
	  • Employee contribution (12 %) + VPF top-up         → deductions
	  • Employer EPF / EPS / EDLI / Admin (statistical)   → earnings

	Gated by a single `epf_applicable` flag on the Employee master.  All
	employees are assumed to be post-1 Sept 2014 EPF members, so the EPS
	rule reduces to: PF wage > ₹15,000 → no EPS, full employer 12 % to EPF.
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

	# Statutory bases
	pf_wage_capped = min(pf_wage, EPF_WAGE_CEILING)
	# Employee + employer EPF base depends on the per-employee toggle.
	# EPS and EDLI are ALWAYS capped at the statutory ceiling.
	epf_base = pf_wage if contribute_on_actual else pf_wage_capped

	# --- Employee side ---------------------------------------------------
	employee_epf = _epfo_round(epf_base * EPF_EMPLOYEE_RATE)
	vpf = _compute_vpf(doc.employee, epf_base)

	# --- Employer side ---------------------------------------------------
	employer_total = _epfo_round(epf_base * EPF_EMPLOYER_RATE)

	if pf_wage > EPF_WAGE_CEILING:
		# Post-2014 high earner — entire employer 12 % goes to EPF (A/c 1).
		# This branch fires regardless of the contribute-on-actual toggle.
		employer_eps = 0
	else:
		employer_eps = _epfo_round(pf_wage_capped * EPS_RATE)

	employer_epf = max(0, employer_total - employer_eps)
	edli = _epfo_round(pf_wage_capped * EDLI_RATE)
	# EPF Admin is 0.5 % of the contribution base.  The EPFO ₹500/establishment
	# monthly minimum is enforced at the establishment level (across all
	# employees) and is out of scope for per-slip computation.
	epf_admin = _epfo_round(epf_base * EPF_ADMIN_RATE)

	_apply_epf_components(
		doc,
		employee_epf=employee_epf,
		vpf=vpf,
		employer_epf=employer_epf,
		employer_eps=employer_eps,
		edli=edli,
		epf_admin=epf_admin,
	)
	_recalculate_totals(doc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_epf_applicable(employee: str) -> bool:
	"""Return True if EPF is opted-in on the Employee master."""
	return bool(frappe.db.get_value("Employee", employee, "epf_applicable"))


def _required_components_exist() -> bool:
	"""All six EPF-scheme salary components must exist before we inject rows."""
	for name in EPF_ALL_COMPONENTS:
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


def _apply_epf_components(
	doc,
	*,
	employee_epf: float,
	vpf: float,
	employer_epf: float,
	employer_eps: float,
	edli: float,
	epf_admin: float,
) -> None:
	"""
	Replace any existing EPF-scheme rows on the slip with freshly computed
	amounts.  Employee rows go into `deductions`, employer rows into
	`earnings` flagged statistical so they're excluded from net pay.
	"""
	# Strip any stale rows (e.g. from a previous save with different config)
	doc.deductions = [d for d in doc.deductions if d.salary_component not in EPF_ALL_COMPONENTS]
	doc.earnings = [e for e in doc.earnings if e.salary_component not in EPF_ALL_COMPONENTS]

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

	for component, amount in (
		(EMPLOYER_EPF_COMPONENT, employer_epf),
		(EMPLOYER_EPS_COMPONENT, employer_eps),
		(EDLI_COMPONENT, edli),
		(EPF_ADMIN_COMPONENT, epf_admin),
	):
		if amount <= 0:
			continue
		doc.append(
			"earnings",
			{
				"salary_component": component,
				"amount": amount,
				"statistical_component": 1,
				"do_not_include_in_total": 1,
			},
		)


def _remove_epf_components(doc) -> None:
	"""Strip EPF-scheme rows from both earnings and deductions; recalculate."""
	d_before = len(doc.deductions)
	e_before = len(doc.earnings)
	doc.deductions = [d for d in doc.deductions if d.salary_component not in EPF_ALL_COMPONENTS]
	doc.earnings = [e for e in doc.earnings if e.salary_component not in EPF_ALL_COMPONENTS]
	if len(doc.deductions) != d_before or len(doc.earnings) != e_before:
		_recalculate_totals(doc)


def _recalculate_totals(doc) -> None:
	"""
	Recompute total_deduction and net_pay after modifying deduction rows.

	Statistical earnings rows we inject (Employer EPF/EPS/EDLI/Admin) carry
	`do_not_include_in_total=1`, so they don't shift gross_pay.  Gross was
	already calculated by the Salary Slip controller before this hook ran;
	we leave it alone.
	"""
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

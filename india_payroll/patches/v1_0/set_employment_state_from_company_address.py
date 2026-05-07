import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""
	Backfill `employment_state` on existing Salary Structure Assignments.

	For each SSA that has no employment_state set, the state is inferred from
	the `state` field on the primary company address (Address doctype linked to
	the SSA's company with is_primary_address = 1).
	"""
	from india_payroll.install import get_custom_fields

	# Ensure the employment_state custom field exists before querying it.
	# This is safe to call multiple times (create_custom_fields is idempotent).
	create_custom_fields(get_custom_fields())

	SalaryStructureAssignment = frappe.qb.DocType("Salary Structure Assignment")

	assignments = (
		frappe.qb.from_(SalaryStructureAssignment)
		.select(SalaryStructureAssignment.name, SalaryStructureAssignment.company)
		.where(
			SalaryStructureAssignment.employment_state.isnull()
			| (SalaryStructureAssignment.employment_state == "")
		)
		.run(as_dict=True)
	)

	if not assignments:
		return

	# Cache: company → state (avoid one DB call per SSA row)
	company_state: dict[str, str] = {}

	for ssa in assignments:
		company = ssa.company

		if company not in company_state:
			address_name = _get_primary_company_address(company)
			state = frappe.db.get_value("Address", address_name, "state") if address_name else None
			company_state[company] = state or ""

		state = company_state[company]
		if state:
			frappe.db.set_value(
				"Salary Structure Assignment",
				ssa.name,
				"employment_state",
				state,
				update_modified=False,
			)


def _get_primary_company_address(company: str) -> str | None:
	"""Return the name of the primary Address record linked to the given company."""
	addresses = frappe.get_all(
		"Address",
		filters=[
			["Dynamic Link", "link_doctype", "=", "Company"],
			["Dynamic Link", "link_name", "=", company],
			["disabled", "=", 0],
		],
		pluck="name",
		order_by="is_primary_address DESC",
		limit=1,
	)
	return addresses[0] if addresses else None

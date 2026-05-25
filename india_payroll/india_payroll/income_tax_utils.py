from frappe.utils import flt
from hrms.payroll.doctype.income_tax_slab.income_tax_slab import calculate_base_tax_from_tax_slabs


def apply_surcharge_with_marginal_relief(
	tax_amount, annual_taxable_earning, tax_slab, eval_globals, eval_locals
):
	"""
	India regional override for apply_surcharge_with_marginal_relief.
	Returns (tax_amount_with_surcharge, total_surcharge).
	Surcharge rows are identified by descriptions starting with "Surcharge".
	Only one surcharge tier fires per income level (non-overlapping min/max ranges).
	"""
	total_surcharge = 0.0
	for surcharge in tax_slab.surcharge_slabs:
		if flt(surcharge.min_taxable_income) and flt(surcharge.min_taxable_income) > annual_taxable_earning:
			continue
		if flt(surcharge.max_taxable_income) and flt(surcharge.max_taxable_income) < annual_taxable_earning:
			continue
		total_surcharge = surcharge_with_marginal_relief(
			surcharge, tax_amount, annual_taxable_earning, tax_slab, eval_globals, eval_locals
		)

	return tax_amount + total_surcharge, total_surcharge


def surcharge_with_marginal_relief(
	surcharge, tax_amount, annual_taxable_earning, tax_slab, eval_globals, eval_locals
):
	raw_surcharge = tax_amount * flt(surcharge.percent) / 100
	threshold = flt(surcharge.min_taxable_income)
	surcharge_rate_previous_slab = get_surcharge_at_previous_slab(threshold, tax_slab)

	base_tax_at_threshold = calculate_base_tax_from_tax_slabs(threshold, tax_slab, eval_globals, eval_locals)
	surcharge_at_threshold = base_tax_at_threshold * surcharge_rate_previous_slab / 100
	total_tax_at_threshold = base_tax_at_threshold + surcharge_at_threshold

	excess_income = annual_taxable_earning - threshold
	excess_tax = (tax_amount + raw_surcharge) - total_tax_at_threshold

	if excess_tax <= excess_income:
		return raw_surcharge
	return max(0.0, raw_surcharge - (excess_tax - excess_income))


def get_surcharge_at_previous_slab(threshold, tax_slab):
	tiers = sorted(
		[c for c in tax_slab.surcharge_slabs],
		key=lambda c: flt(c.min_taxable_income),
	)
	for i, tier in enumerate(tiers):
		if flt(tier.min_taxable_income) == threshold:
			return flt(tiers[i - 1].percent) if i > 0 else 0.0
	return 0.0

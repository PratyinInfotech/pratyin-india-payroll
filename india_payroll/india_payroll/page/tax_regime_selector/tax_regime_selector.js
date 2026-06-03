// Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.pages["tax-regime-selector"].on_page_load = function (wrapper) {
	new TaxRegimeSelector(wrapper);
};

class TaxRegimeSelector {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Tax Regime Selector"),
			single_column: true,
		});
		this.employee_data = null;
		this.declarations = {};
		this.rent_monthly = 0;
		this.city_type = "non-metro";
		this.annual_gross = 0;
		this.setup_employee_filter();
	}

	setup_employee_filter() {
		$(this.page.main).html(`
			<div style="padding: 20px;">
				<div style="display:flex; gap:16px; align-items:center;">
					<div style="flex:0 0 65%; max-width:65%; display:flex; gap:16px; min-width:0;">
						<div style="flex:1; min-width:0;"><div id="payroll-period-wrapper"></div></div>
						<div style="flex:1; min-width:0;"><div id="employee-field-wrapper"></div></div>
						<div style="flex:1; min-width:0; overflow:hidden;"><div id="annual-gross-wrapper"></div></div>
					</div>
					<div style="flex:1; min-width:0;" id="comparison-alert"></div>
				</div>
				<div id="page-body" style="margin-top: 20px;"></div>
			</div>
		`);

		this.payroll_period_control = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				options: "Payroll Period",
				fieldname: "payroll_period",
				label: __("Payroll Period"),
				reqd: 1,
				read_only: 1,
			},
			parent: document.getElementById("payroll-period-wrapper"),
			render_input: true,
		});
		this.payroll_period_control.refresh();

		this.employee_control = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				options: "Employee",
				fieldname: "employee",
				label: __("Employee"),
				placeholder: __("Select Employee"),
				reqd: 1,
				change: () => {
					const employee = this.employee_control.get_value();
					if (employee) {
						this.load_employee(employee);
					} else {
						this.annual_gross_control.set_value("");
						this.render_placeholder();
					}
				},
			},
			parent: document.getElementById("employee-field-wrapper"),
			render_input: true,
		});
		this.employee_control.refresh();

		this.annual_gross_control = frappe.ui.form.make_control({
			df: {
				fieldtype: "Currency",
				fieldname: "annual_gross",
				label: __("Annual Gross (₹)"),
				reqd: 1,
				change: () => {
					const val = flt(this.annual_gross_control.get_value());
					if (val > 0) {
						this.annual_gross = val;
						if (this.employee_data) this.compute();
					}
				},
			},
			parent: document.getElementById("annual-gross-wrapper"),
			render_input: true,
		});
		this.annual_gross_control.refresh();

		this.fetch_payroll_period();
		frappe.call({
			method: "india_payroll.india_payroll.page.tax_regime_selector.tax_regime_selector.setup_if_missing",
		});
	}

	fetch_payroll_period() {
		frappe.call({
			method: "india_payroll.india_payroll.page.tax_regime_selector.tax_regime_selector.get_current_payroll_period",
			callback: (r) => {
				if (!r.message?.payroll_period) {
					frappe.msgprint({
						title: __("Payroll Period Not Found"),
						message: __(
							"No active Payroll Period found for today's date. Please create a Payroll Period that includes today before proceeding."
						),
						indicator: "red",
						primary_action: {
							label: __("Create Payroll Period"),
							action: () => frappe.new_doc("Payroll Period"),
						},
					});
					return;
				}
				this.payroll_period_control.set_value(r.message.payroll_period);
			},
		});
	}

	render_placeholder() {
		$("#comparison-alert").html("");
		$("#page-body").html(`
			<div class="text-center text-muted" style="padding: 60px 0; font-size: var(--text-lg);">
				${__("Select an employee to compare tax regimes")}
			</div>
		`);
	}

	load_employee(employee) {
		frappe.call({
			method: "india_payroll.india_payroll.page.tax_regime_selector.tax_regime_selector.get_employee_details",
			args: { employee },
			callback: (r) => {
				this.employee_data = r.message;
				this.declarations = {};
				this.rent_monthly = 0;
				this.city_type = "non-metro";
				this.annual_gross = flt(r.message.annual_gross);
				this.payroll_period_control.set_value(r.message.payroll_period);
				this.annual_gross_control.set_value(r.message.annual_gross);
				this.render_page();
				this.compute();
			},
		});
	}

	render_page() {
		const is_senior = this.employee_data.is_senior_citizen;
		const cats = (this.employee_data.exemption_categories || []).filter((c) => {
			if (this.employee_data.has_hra && c.name === "80GG") return false;
			if (c.name === "80CCD(2)") return false;
			if (is_senior && c.name === "80TTA") return false;
			if (!is_senior && c.name === "80TTB") return false;
			return true;
		});
		this._cat_map = Object.fromEntries(cats.map((c) => [c.name, c]));
		this._declaration_cats = cats;

		$("#page-body").html(`
			<div style="display:flex; gap:15px; align-items:flex-start;">
				<div style="flex:0 0 65%; max-width:65%; min-width:0;">
					<div class="frappe-card" style="padding: 16px; max-height:80vh; overflow-y:auto;">
						${
							this.employee_data.has_hra
								? `
						<h6 class="form-section-heading uppercase">${__("Section 10")}</h6>
						${this.render_section10_inputs()}`
								: ""
						}
						<div style="display:flex; justify-content:space-between; align-items:center; margin-top:32px; margin-bottom:12px;">
							<h6 class="form-section-heading uppercase" style="margin:0;">${__("Chapter VI-A Deductions")}</h6>
							<div>
								<button class="btn btn-xs btn-default" id="expand-all-btn" style="margin-right:4px;">${__(
									"Expand All"
								)}</button>
								<button class="btn btn-xs btn-default" id="collapse-all-btn">${__("Collapse All")}</button>
							</div>
						</div>
						<div id="declaration-table-wrapper"></div>
					</div>
				</div>
				<div style="flex:0 0 35%; max-width:35%; min-width:0; position:sticky; top:0; margin-right:15px;" id="comparison-panel">
					<div class="text-center text-muted" style="padding: 40px 0;">
						${__("Computing...")}
					</div>
				</div>
			</div>
		`);
		this.bind_input_events();
		this.setup_declaration_datatable();
	}

	render_section10_inputs() {
		return `<div class="row" style="margin-bottom:20px;">
			<div class="col-md-4">
				<div class="form-group">
					<label class="control-label">${__("Monthly Rent (₹)")}</label>
					<div class="control-input">
						<input type="text" inputmode="decimal" class="form-control regime-input"
							data-key="rent_monthly">
					</div>
				</div>
			</div>
			<div class="col-md-6">
				<label style="display:flex; align-items:flex-start; gap:8px; cursor:pointer; font-weight:var(--weight-medium); margin:0;">
					<input type="checkbox" class="regime-input" data-key="city_type" style="margin-top:3px; flex-shrink:0;">
					<span>
						${__("Rented in Metro City")}
						<div class="text-extra-muted" style="margin-top:3px;font-size:var(--text-sm)">
							${__(
								"Metro cities include Mumbai, Delhi, Chennai, Kolkata, Ahmedabad, Bengaluru, Pune, Hyderabad"
							)}
						</div>
					</span>
				</label>
			</div>
		</div>`;
	}

	setup_declaration_datatable() {
		const cats = this._declaration_cats;
		if (!cats.length) return;

		this._sub_amounts = {};
		cats.forEach((cat) => {
			this._sub_amounts[cat.name] = {};
		});

		const expanded_icon = frappe.utils.icon("es-line-down", "sm");
		const collapsed_icon = frappe.utils.icon("chevron-right", "sm");

		const rows = cats
			.map((cat) => {
				const sub_rows = (cat.sub_categories || [])
					.map(
						(sub) => `
				<tr class="section-sub-row" data-section-parent="${cat.name}"
					style="height:64px; border-bottom:1px solid var(--border-color);">
					<td style="padding:0 12px 0 32px;">${sub.name}</td>
					<td class="text-right text-muted" style="padding:0 12px;">${
						sub.max_amount ? this.fmt(sub.max_amount) : ""
					}</td>
					<td class="text-right" style="padding:0 12px;">
						<input type="number" class="form-control input-sm declaration-input"
							data-section="${cat.name}"
							data-sub="${sub.name}"
							${sub.max_amount ? `max="${sub.max_amount}"` : ""}
							min="0"
							style="width:100%; text-align:right; -moz-appearance:textfield;">
					</td>
				</tr>`
					)
					.join("");

				const desc = cat.description
					? `<div class="help-box small text-extra-muted" style="padding-left:0; margin-bottom:0;">${cat.description}</div>`
					: "";

				return `
				<tr class="section-header-row" data-section-id="${cat.name}"
					style="border-bottom:1px solid var(--border-color); cursor:pointer;">
					<td style="padding:14px 12px;">
						<div style="display:flex; align-items:flex-start; gap:4px;">
							<span class="section-toggle" style="display:inline-flex; flex-shrink:0; width:16px; margin-top:2px; transition:transform 0.15s;">${expanded_icon}</span>
							<div>
								<strong>${cat.name}</strong>
								${desc}
							</div>
						</div>
					</td>
					<td class="text-right text-muted" style="padding:14px 12px; vertical-align:top;">${
						cat.max_amount ? this.fmt(cat.max_amount) : "-"
					}</td>
					<td class="text-right" data-total-for="${
						cat.name
					}" style="padding:14px 12px; vertical-align:top; color:var(--text-muted);">${this.fmt(
					0
				)}</td>
				</tr>
				${sub_rows}`;
			})
			.join("");

		const wrapper = document.getElementById("declaration-table-wrapper");
		wrapper.innerHTML = `
			<style>
				.declaration-input::-webkit-outer-spin-button,
				.declaration-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
			</style>
			<table style="width:100%; table-layout:fixed; border-collapse:collapse;" class="declaration-table">
				<colgroup>
					<col style="width:50%">
					<col style="width:20%">
					<col style="width:30%">
				</colgroup>
				<thead>
					<tr style="border-bottom:2px solid var(--border-color); background:var(--gray-50);">
						<th style="padding:10px 12px; font-weight:500; color:var(--text-muted);">${__(
							"Deduction / Investment"
						)}</th>
						<th style="padding:10px 12px; font-weight:500; color:var(--text-muted); text-align:right;">${__(
							"Limit"
						)}</th>
						<th style="padding:10px 12px; font-weight:500; color:var(--text-muted); text-align:right;">${__(
							"Declared Amount"
						)}</th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>`;

		this._total_cells = {};
		wrapper.querySelectorAll("[data-total-for]").forEach((td) => {
			this._total_cells[td.dataset.totalFor] = td;
		});

		wrapper.querySelectorAll(".section-header-row").forEach((row) => {
			row.addEventListener("click", () => {
				const $row = $(row);
				const sub_rows = $row.nextUntil(".section-header-row");
				const toggle = $row.find(".section-toggle");
				const collapsed = sub_rows.first().is(":hidden");
				sub_rows.toggle(collapsed);
				toggle.html(collapsed ? expanded_icon : collapsed_icon);
			});
		});

		document.getElementById("expand-all-btn").addEventListener("click", () => {
			wrapper.querySelectorAll(".section-sub-row").forEach((r) => $(r).show());
			wrapper.querySelectorAll(".section-toggle").forEach((t) => {
				t.innerHTML = expanded_icon;
			});
		});
		document.getElementById("collapse-all-btn").addEventListener("click", () => {
			wrapper.querySelectorAll(".section-sub-row").forEach((r) => $(r).hide());
			wrapper.querySelectorAll(".section-toggle").forEach((t) => {
				t.innerHTML = collapsed_icon;
			});
		});
	}

	bind_input_events() {
		$("#page-body").on("change", ".regime-input", () => {
			this.collect_section10_inputs();
			this.compute();
		});
		$("#page-body").on("change", ".declaration-input", (e) => {
			const el = e.currentTarget;
			const section = $(el).data("section");
			const sub = $(el).data("sub");
			const amount = flt($(el).val());
			if (amount > 0) {
				this._sub_amounts[section][sub] = amount;
			} else {
				delete this._sub_amounts[section][sub];
			}
			const total = Object.values(this._sub_amounts[section]).reduce((a, b) => a + b, 0);
			if (total > 0) {
				this.declarations[section] = total;
			} else {
				delete this.declarations[section];
			}
			if (this._total_cells?.[section]) {
				this._total_cells[section].textContent = total > 0 ? this.fmt(total) : "";
				this._total_cells[section].style.fontWeight = total > 0 ? "600" : "";
			}
			this.compute();
		});
	}

	collect_section10_inputs() {
		$("#page-body")
			.find(".regime-input")
			.each((_, el) => {
				const key = $(el).data("key");
				if (key === "rent_monthly") {
					this.rent_monthly = flt($(el).val());
				} else if (key === "city_type") {
					this.city_type = $(el).is(":checked") ? "metro" : "non-metro";
				}
			});
	}

	compute() {
		const employee = this.employee_control.get_value();
		frappe.call({
			method: "india_payroll.india_payroll.page.tax_regime_selector.tax_regime_selector.compute_tax_comparison",
			args: {
				employee,
				declarations: this.declarations,
				rent_monthly: this.rent_monthly,
				city_type: this.city_type,
				annual_gross: this.annual_gross,
			},
			callback: (r) => this.render_comparison(r.message),
		});
	}

	render_comparison(result) {
		const old = result.old_regime;
		const new_ = result.new_regime;
		const old_wins = result.recommended === "old";
		const savings = result.savings;

		const regime_card = (label, regime, is_winner) => `
			<div class="frappe-card" style="padding: 16px;">
				<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; gap:6px;">
					<strong style="white-space:nowrap;">${label}</strong>
					${
						is_winner
							? `<span class="badge indicator-pill green no-indicator-dot" style="flex-shrink:0;">${__(
									"Suggested"
							  )}</span>`
							: ""
					}
				</div>
				<div class="text-muted" style="font-size: var(--text-xs); margin-bottom: 4px;">${__(
					"Taxable Income"
				)}</div>
				<div style="font-size: var(--text-lg); font-weight: 600; margin-bottom: 12px;">${this.fmt(
					regime.taxable_income
				)}</div>
				<div class="text-muted" style="font-size: var(--text-xs); margin-bottom: 4px;">${__(
					"Tax + Cess"
				)}</div>
				<div style="font-size: var(--text-2xl); font-weight: 700; color: ${
					is_winner ? "var(--primary)" : "inherit"
				};">${this.fmt(regime.tax)}</div>
				<div style="margin-top: 16px;">
					<button class="btn btn-${is_winner ? "primary" : "default"} btn-block btn-sm select-regime-btn"
						data-slab="${regime.slab}">
						${__("Select")}
					</button>
				</div>
			</div>`;

		const winner_label = old_wins
			? __("Old Regime saves {0} over New Regime", [this.fmt(savings)])
			: __("New Regime saves {0} over Old Regime", [this.fmt(savings)]);

		const { top, middle, bottom } = this.build_comparison_rows(old, new_);

		const col_th = (label, star) =>
			`<th class="text-right" style="padding:8px;">${label}${star ? " ★" : ""}</th>`;
		const thead = `<tr style="background:var(--gray-50);">
			<th style="padding:8px;">${__("Item")}</th>
			${col_th(__("Old Regime"), old_wins)}
			${col_th(__("New Regime"), false)}
		</tr>`;

		const colgroup = `<colgroup><col style="width:50%"><col style="width:25%"><col style="width:25%"></colgroup>`;

		$("#comparison-alert").html("");

		const html = `
			<div class="form-message green" style="margin-bottom:12px; font-weight:normal; margin-right:15px;">
				${winner_label}
			</div>
			<div style="display:flex; gap:15px; margin-bottom:12px; margin-right:15px; overflow-x:auto;">
				<div style="flex:1 0 185px;">${regime_card(__("Old Regime"), old, old_wins)}</div>
				<div style="flex:1 0 185px;">${regime_card(__("New Regime"), new_, !old_wins)}</div>
			</div>
			<div style="display:flex; flex-direction:column; border:1px solid var(--border-color); border-radius:var(--border-radius); overflow:hidden; font-size:var(--text-sm); margin-right:15px;">
				<table style="width:100%; border-collapse:collapse; table-layout:fixed;">
					${colgroup}
					<thead>${thead}</thead>
					<tbody>${top}</tbody>
				</table>
				<div style="overflow-y:auto; max-height:calc(80vh - 500px); border-top:1px solid var(--border-color);">
					<table style="width:100%; border-collapse:collapse; table-layout:fixed;">
						${colgroup}
						<tbody>${middle}</tbody>
					</table>
				</div>
				<table style="width:100%; border-collapse:collapse; table-layout:fixed; border-top:2px solid var(--border-color);">
					${colgroup}
					<tbody>${bottom}</tbody>
				</table>
			</div>
			<div style="text-align:right; margin-top:12px; margin-right:15px;">
				<button class="btn btn-default btn-sm declare-btn">
					${__("Declare Tax Exemptions →")}
				</button>
			</div>`;

		$("#comparison-panel").html(html);
		this.bind_action_buttons();
	}

	build_comparison_rows(old, new_) {
		const make_row = (label, old_val, new_val, bold = false) => {
			const s = bold ? "font-weight:600;" : "";
			const cell = (v) =>
				v !== null && v !== undefined
					? `<td class="text-right" style="${s} padding:8px;">${this.fmt(v)}</td>`
					: `<td class="text-right text-muted" style="${s} padding:8px;">—</td>`;
			return `<tr><td style="${s} padding:8px;">${label}</td>${cell(old_val)}${cell(
				new_val
			)}</tr>`;
		};

		const ob = old.breakdown;
		const nb = new_.breakdown;

		const top = make_row(__("Gross Income"), ob.gross, nb.gross);

		const middle_rows = [];
		middle_rows.push(
			make_row(__("Standard Deduction"), -ob.standard_deduction, -nb.standard_deduction)
		);
		if (ob.hra_exemption) {
			middle_rows.push(make_row(__("HRA - Section 10(13A)"), -ob.hra_exemption, null));
		}
		if (ob.lta_exemption) {
			middle_rows.push(make_row(__("LTA - Section 10(5)"), -ob.lta_exemption, null));
		}
		if (ob.employer_nps || nb.employer_nps) {
			middle_rows.push(
				make_row(
					__("Employer NPS - 80CCD(2)"),
					ob.employer_nps ? -ob.employer_nps : null,
					nb.employer_nps ? -nb.employer_nps : null
				)
			);
		}
		Object.entries(ob.via_deductions || {}).forEach(([section, amount]) => {
			if (amount > 0) middle_rows.push(make_row(section, -amount, null));
		});

		const bottom = [
			make_row(__("Taxable Income"), ob.taxable_income, nb.taxable_income, true),
			make_row(__("Income Tax + Cess"), old.tax, new_.tax, true),
		].join("");

		return { top, middle: middle_rows.join(""), bottom };
	}

	bind_action_buttons() {
		$("#page-body")
			.find(".select-regime-btn")
			.on("click", (e) => {
				const slab = $(e.currentTarget).data("slab");
				const employee = this.employee_control.get_value();
				frappe.confirm(__("Set income tax slab to {0} for {1}?", [slab, employee]), () => {
					frappe.call({
						method: "india_payroll.india_payroll.page.tax_regime_selector.tax_regime_selector.set_tax_regime",
						args: { employee, income_tax_slab: slab },
						callback: () => {
							frappe.show_alert({
								message: __("Tax regime updated"),
								indicator: "green",
							});
						},
					});
				});
			});

		$("#page-body")
			.find(".declare-btn")
			.on("click", () => {
				const employee = this.employee_control.get_value();
				const payroll_period = this.payroll_period_control.get_value();
				const entries = [];
				Object.entries(this._sub_amounts || {}).forEach(([section, subs]) => {
					Object.entries(subs).forEach(([sub_name, amount]) => {
						if (amount > 0) {
							entries.push({
								exemption_category: section,
								exemption_sub_category: sub_name,
								amount,
							});
						}
					});
				});

				frappe.route_hooks.after_load = (frm) => {
					frm.set_value("employee", employee);
					frm.set_value("payroll_period", payroll_period);
					entries.forEach((e) => {
						const row = frappe.model.add_child(frm.doc, "declarations");
						frappe.model.set_value(
							row.doctype,
							row.name,
							"exemption_category",
							e.exemption_category
						);
						frappe.model.set_value(
							row.doctype,
							row.name,
							"exemption_sub_category",
							e.exemption_sub_category
						);
						frappe.model.set_value(row.doctype, row.name, "amount", e.amount);
					});
					frm.refresh_fields();
				};
				frappe.new_doc("Employee Tax Exemption Declaration");
			});
	}

	fmt(n) {
		return "₹" + Math.round(n || 0).toLocaleString("en-IN");
	}
}

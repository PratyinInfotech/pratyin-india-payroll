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
		this.selected_slab = null;
		this.setup_employee_filter();
	}

	setup_employee_filter() {
		$(this.page.main).html(`
			<style>
				.regime-radio-card { transition: box-shadow 0.1s; }
				.regime-radio-card:hover { box-shadow: 0 0 0 1px var(--gray-400); }
				.section-header-row:hover { background: var(--gray-50); }
			</style>
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
				fieldname: "annual_gross_earning",
				label: __("Annual Gross Earning"),
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

		// Default to the logged-in user's employee, if any.
		window.hrms?.get_current_employee?.().then((employee) => {
			if (employee) this.employee_control.set_value(employee);
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
		this.page.clear_primary_action();
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
				this.rent_monthly = 0;
				this.city_type = "non-metro";
				this.annual_gross = flt(r.message.annual_gross);
				// Reflect the employee's current regime on load; stage starts at saved.
				this.selected_slab = r.message.current_income_tax_slab || null;
				this.staged_slab = this.selected_slab;
				// Submitted SSAs are read-only (radios + Save Regime hidden).
				this.is_submitted = r.message.ssa_docstatus === 1;

				// Prefill statutory deductions (EPF, employee NPS) matched on the server.
				this._prefill = r.message.prefill_declarations || {};
				this.declarations = {};
				Object.entries(this._prefill).forEach(([section, subs]) => {
					const total = Object.values(subs).reduce((a, b) => a + flt(b), 0);
					if (total > 0) this.declarations[section] = total;
				});

				this.payroll_period_control.set_value(r.message.payroll_period);
				this.annual_gross_control.set_value(r.message.annual_gross);
				frappe.call({
					method: "india_payroll.india_payroll.page.tax_regime_selector.tax_regime_selector.compute_tax_comparison",
					args: {
						employee,
						declarations: this.declarations,
						rent_monthly: 0,
						city_type: "non-metro",
						annual_gross: this.annual_gross,
					},
					callback: (comp) => {
						this.render_page();
						this.render_comparison(comp.message);
					},
				});
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
					<div class="frappe-card" style="padding: 16px; max-height:80vh; display:flex; flex-direction:column;">
						<div style="display:flex; justify-content:flex-end; flex-shrink:0; margin-bottom:12px;">
							<button class="btn btn-default btn-sm declare-btn">
								${__("Declare Tax Exemptions →")}
							</button>
						</div>
						<div style="overflow-y:auto; overflow-x:hidden; flex:1; min-height:0;">
							${
								this.employee_data.has_hra
									? `
							<h6 class="form-section-heading uppercase">${__("Section 10")}</h6>
							${this.render_section10_inputs()}`
									: ""
							}
							<div style="display:flex; justify-content:space-between; align-items:center; gap:12px; ${
								this.employee_data.has_hra ? "margin-top:32px;" : ""
							} margin-bottom:12px;">
								<h6 class="form-section-heading uppercase" style="margin:0; white-space:nowrap;">${__(
									"Chapter VI-A Deductions"
								)}</h6>
								<div style="display:flex; align-items:center; gap:8px;">
									<div style="position:relative;" id="declaration-search-wrapper">
										<span style="position:absolute; left:8px; top:50%; transform:translateY(-50%); display:inline-flex; color:var(--text-muted); pointer-events:none;">
											<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
										</span>
										<input type="text" class="form-control input-sm" id="declaration-search"
											placeholder="${__("Search")}" style="padding-left:28px;">
									</div>
									<button class="btn btn-xs btn-default" id="expand-all-btn">${__("Expand All")}</button>
									<button class="btn btn-xs btn-default" id="collapse-all-btn">${__("Collapse All")}</button>
								</div>
							</div>
							<div id="declaration-table-wrapper"></div>
							<div id="declaration-empty" class="text-muted text-center" style="display:none; padding:20px;">
								${__("No deductions found")}
							</div>
						</div>
					</div>
				</div>
				<div style="flex:0 0 35%; max-width:35%; min-width:0; position:sticky; top:0; margin-right:15px; max-height:80vh; display:flex; flex-direction:column;" id="comparison-panel">
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

		// Seed per-section amounts from the server-matched prefill (EPF, NPS).
		const prefill = this._prefill || {};
		this._sub_amounts = {};
		cats.forEach((cat) => {
			this._sub_amounts[cat.name] = { ...(prefill[cat.name] || {}) };
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
					<tr>
						<th style="padding:10px 12px; font-weight:500; color:var(--text-muted); position:sticky; top:-1px; z-index:1; background:var(--gray-50); box-shadow:inset 0 -2px 0 var(--border-color);">${__(
							"Deduction / Investment"
						)}</th>
						<th style="padding:10px 12px; font-weight:500; color:var(--text-muted); text-align:right; position:sticky; top:-1px; z-index:1; background:var(--gray-50); box-shadow:inset 0 -2px 0 var(--border-color);">${__(
							"Limit"
						)}</th>
						<th style="padding:10px 12px; font-weight:500; color:var(--text-muted); text-align:right; position:sticky; top:-1px; z-index:1; background:var(--gray-50); box-shadow:inset 0 -2px 0 var(--border-color);">${__(
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

		// Reflect prefilled (EPF/NPS) amounts into the sub-category inputs and section totals.
		Object.entries(this._sub_amounts).forEach(([section, subs]) => {
			Object.entries(subs).forEach(([sub, amount]) => {
				const input = wrapper.querySelector(
					`.declaration-input[data-section="${section}"][data-sub="${sub}"]`
				);
				if (input) input.value = amount;
			});
			const total = Object.values(subs).reduce((a, b) => a + flt(b), 0);
			if (this._total_cells[section]) {
				this._total_cells[section].textContent = total > 0 ? this.fmt(total) : this.fmt(0);
				this._total_cells[section].style.fontWeight = total > 0 ? "600" : "";
			}
		});

		const search = document.getElementById("declaration-search");
		if (search) {
			search.addEventListener("input", (e) => this.filter_declarations(e.target.value));
			// Match the search box width to the Declared Amount input column.
			const sample_input = wrapper.querySelector(".declaration-input");
			const search_wrapper = document.getElementById("declaration-search-wrapper");
			if (sample_input && search_wrapper) {
				search_wrapper.style.width = sample_input.offsetWidth + "px";
			}
		}

		const section_states = new Map();

		$(wrapper).on("click", ".section-header-row", function () {
			const section_id = $(this).data("section-id");
			const is_collapsed = section_states.get(section_id) || false;
			const $row = $(this);
			const sub_rows = $row.nextUntil(".section-header-row");
			const toggle = $row.find(".section-toggle");
			if (is_collapsed) {
				sub_rows.show();
				toggle.html(expanded_icon);
				section_states.set(section_id, false);
			} else {
				sub_rows.hide();
				toggle.html(collapsed_icon);
				section_states.set(section_id, true);
			}
		});

		document.getElementById("expand-all-btn").addEventListener("click", () => {
			wrapper.querySelectorAll(".section-sub-row").forEach((r) => $(r).show());
			wrapper.querySelectorAll(".section-toggle").forEach((t) => {
				t.innerHTML = expanded_icon;
			});
			section_states.forEach((_, k) => section_states.set(k, false));
		});
		document.getElementById("collapse-all-btn").addEventListener("click", () => {
			wrapper.querySelectorAll(".section-sub-row").forEach((r) => $(r).hide());
			wrapper.querySelectorAll(".section-toggle").forEach((t) => {
				t.innerHTML = collapsed_icon;
			});
			section_states.forEach((_, k) => section_states.set(k, true));
		});
	}

	filter_declarations(query) {
		const q = (query || "").trim().toLowerCase();
		const wrapper = document.getElementById("declaration-table-wrapper");
		if (!wrapper) return;

		let any_section_visible = false;
		wrapper.querySelectorAll(".section-header-row").forEach((header) => {
			const $header = $(header);
			const sub_rows = $header.nextUntil(".section-header-row");
			const header_text = $header.text().toLowerCase();
			const header_match = header_text.includes(q);

			let any_sub_match = false;
			sub_rows.each((_, sub) => {
				// A sub is visible if it matches, or its section header matches.
				const match = !q || header_match || $(sub).text().toLowerCase().includes(q);
				$(sub).toggle(match);
				if (match) any_sub_match = true;
			});

			const header_visible = !q || header_match || any_sub_match;
			$header.toggle(header_visible);
			if (header_visible) any_section_visible = true;
		});

		$("#declaration-empty").toggle(!any_section_visible);
	}

	bind_input_events() {
		// Namespaced + .off first so repeated employee loads don't stack handlers.
		const $body = $("#page-body").off(".trs");

		$body.on("change.trs", ".regime-input", () => {
			this.collect_section10_inputs();
			this.compute();
		});

		$body.on("change.trs", ".declaration-input", (e) => {
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
				this._total_cells[section].textContent = this.fmt(total);
				this._total_cells[section].style.fontWeight = total > 0 ? "600" : "";
			}
			this.compute();
		});

		$body.on("click.trs", ".declare-btn", () => this.declare_exemptions());

		// Radios stage the choice; the toolbar's Save Regime action commits it.
		$body.on("change.trs", ".regime-radio", (e) => {
			this.staged_slab = $(e.currentTarget).val();
			if (this._last_result) this.render_comparison(this._last_result);
		});
	}

	save_regime() {
		const slab = this.staged_slab;
		if (!slab) return;
		const employee = this.employee_control.get_value();
		frappe.confirm(__("Set income tax slab to {0} for {1}?", [slab, employee]), () => {
			frappe.call({
				method: "india_payroll.india_payroll.page.tax_regime_selector.tax_regime_selector.set_tax_regime",
				args: { employee, income_tax_slab: slab },
				callback: (r) => {
					const assignment = r.message?.assignment;
					const link = assignment
						? `<a href="${frappe.utils.get_form_link(
								"Salary Structure Assignment",
								assignment
						  )}">${assignment}</a>`
						: "";
					frappe.show_alert({
						message: __("Tax Regime updated in Salary Structure Assignment {0}", [
							link,
						]),
						indicator: "green",
					});
					this.selected_slab = slab;
					if (this._last_result) this.render_comparison(this._last_result);
				},
			});
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
			callback: (r) => {
				this._last_result = r.message;
				this.render_comparison(r.message);
			},
		});
	}

	render_comparison(result) {
		const old = result.old_regime;
		const new_ = result.new_regime;
		const old_wins = result.recommended === "old";
		const savings = result.savings;

		const is_tie = savings === 0;

		// A regime choice rendered as a radio card. Picking it stages the choice; the
		// staged card gets a colored border (green, or blue on a tie). Label precedence
		// is Selected > Suggested/Default.
		const regime_card = (label, regime, is_winner, tie_pill) => {
			const is_staged = this.staged_slab === regime.slab;
			const is_selected = this.selected_slab === regime.slab;

			let pill_color = "";
			let pill_label = "";
			if (is_selected) {
				pill_color = "green";
				pill_label = __("Selected");
			} else if (is_tie) {
				if (tie_pill) {
					pill_color = "blue";
					pill_label = __("Default");
				}
			} else if (is_winner) {
				pill_color = "green";
				pill_label = __("Suggested");
			}

			const pill_html = pill_label
				? `<span class="badge indicator-pill ${pill_color} no-indicator-dot" style="flex-shrink:0;">${pill_label}</span>`
				: "";

			const border = is_staged
				? is_tie
					? "var(--blue-500)"
					: "var(--green-500)"
				: "var(--border-color)";

			const radio_html = this.is_submitted
				? ""
				: `<input type="radio" name="regime-choice" class="regime-radio" value="${
						regime.slab
				  }" ${
						is_staged ? "checked" : ""
				  } style="width:16px; height:16px; margin:0; flex-shrink:0;">`;

			return `
			<label class="regime-radio-card frappe-card" style="flex:1 1 200px; min-width:200px; max-width:100%; margin:0; padding:14px 16px; ${
				this.is_submitted ? "" : "cursor:pointer;"
			} display:block;
				border:1px solid ${border};">
				<div style="display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:8px;">
					<strong style="white-space:nowrap;">${label}</strong>
					${radio_html}
				</div>
				<div class="text-muted" style="font-size:var(--text-sm); margin-bottom:4px;">${__(
					"Tax + Cess"
				)}</div>
				<div style="display:flex; align-items:flex-end; justify-content:space-between; gap:8px;">
					<span style="font-size:var(--text-2xl); font-weight:700; line-height:1; color:${
						is_winner ? "var(--primary)" : "inherit"
					};">${this.fmt(regime.tax)}</span>
					${pill_html}
				</div>
			</label>`;
		};

		const alert_color = is_tie ? "blue" : "green";
		const winner_label = is_tie
			? __("Tax payable will be same for both the regimes")
			: old_wins
			? __("Old Regime saves {0} over New Regime", [this.fmt(savings)])
			: __("New Regime saves {0} over Old Regime", [this.fmt(savings)]);

		const { top, middle, bottom } = this.build_comparison_rows(old, new_);

		const col_th = (label, star) =>
			`<th class="text-right" style="padding:8px;">${label}${star ? " ★" : ""}</th>`;
		const thead = `<tr style="background:var(--gray-50);">
			<th style="padding:8px;">${__("Item")}</th>
			${col_th(__("Old Regime"), !is_tie && old_wins)}
			${col_th(__("New Regime"), false)}
		</tr>`;

		const colgroup = `<colgroup><col style="width:50%"><col style="width:25%"><col style="width:25%"></colgroup>`;

		$("#comparison-alert").html("");

		// Save Regime lives in the page toolbar (top-right); shown only for editable
		// (draft) assignments when a regime is selected. Submitted SSAs are read-only.
		if (this.staged_slab && !this.is_submitted) {
			this.page.set_primary_action(__("Save Regime"), () => this.save_regime());
		} else {
			this.page.clear_primary_action();
		}

		const html = `
			<div style="display:flex; flex-wrap:wrap; gap:15px; margin-bottom:12px; margin-right:15px; align-items:stretch; flex-shrink:0;">
				${regime_card(__("Old Regime"), old, !is_tie && old_wins, false)}
				${regime_card(__("New Regime"), new_, !is_tie && !old_wins, true)}
			</div>
			<div class="form-message ${alert_color}" style="margin-bottom:12px; font-weight:normal; margin-right:15px; flex-shrink:0;">
				${winner_label}
			</div>
			<div style="display:flex; flex-direction:column; border:1px solid var(--border-color); border-radius:var(--border-radius); overflow:hidden; font-size:var(--text-sm); margin-right:15px; flex:1; min-height:0;">
				<table style="width:100%; border-collapse:collapse; table-layout:fixed; flex-shrink:0;">
					${colgroup}
					<thead>${thead}</thead>
					<tbody>${top}</tbody>
				</table>
				<div style="overflow-y:auto; flex:1; min-height:0; border-top:1px solid var(--border-color);">
					<table style="width:100%; border-collapse:collapse; table-layout:fixed;">
						${colgroup}
						<tbody>${middle}</tbody>
					</table>
				</div>
				<table style="width:100%; border-collapse:collapse; table-layout:fixed; border-top:2px solid var(--border-color); flex-shrink:0;">
					${colgroup}
					<tbody>${bottom}</tbody>
				</table>
			</div>`;

		$("#comparison-panel").html(html);
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

	declare_exemptions() {
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

		const rent_monthly = this.rent_monthly;
		const city_type = this.city_type;
		const has_hra = this.employee_data?.has_hra;

		frappe.route_hooks.after_load = (frm) => {
			if (frm.doctype !== "Employee Tax Exemption Declaration") return;
			frm.set_value("employee", employee);
			frm.set_value("payroll_period", payroll_period);
			if (has_hra && rent_monthly > 0) {
				frm.set_value("monthly_house_rent", rent_monthly);
				frm.set_value("rented_in_metro_city", city_type === "metro" ? 1 : 0);
			}
			entries.forEach((e) => {
				const row = frappe.model.add_child(frm.doc, "declarations");
				row.exemption_category = e.exemption_category;
				row.exemption_sub_category = e.exemption_sub_category;
				row.amount = e.amount;
			});
			frm.refresh_field("declarations");
			delete frappe.route_hooks.after_load;
		};
		frappe.new_doc("Employee Tax Exemption Declaration");
	}

	fmt(n) {
		return "₹" + Math.round(n || 0).toLocaleString("en-IN");
	}
}

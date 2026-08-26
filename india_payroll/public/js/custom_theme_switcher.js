// Adds a fourth "Custom" option to the built-in Switch Theme dialog (alongside
// Frappe Light / Timeless Night / Automatic) without touching the three stock
// themes. Selection is remembered in localStorage rather than the User's
// `desk_theme` field, since that field's options and the server-side
// `switch_theme` whitelist only accept Light/Dark/Automatic.
//
// Custom is the deployment default: it applies on load for every browser
// unless that browser has explicitly picked Light/Dark/Automatic from the
// Switch Theme dialog before (OPT_OUT_KEY). Picking "Custom" again clears
// the opt-out so it goes back to being automatic. The legacy opt-in key is
// still honored so anyone who already turned it on before this default
// flipped keeps seeing it without any change on their end.
(function () {
	const LEGACY_OPT_IN_KEY = "india_payroll_custom_theme_enabled";
	const OPT_OUT_KEY = "india_payroll_custom_theme_disabled";

	function apply_custom_theme() {
		document.documentElement.setAttribute("data-theme-mode", "custom");
		document.documentElement.setAttribute("data-theme", "custom");
	}

	const opted_out = localStorage.getItem(OPT_OUT_KEY) === "1";
	if (!opted_out || localStorage.getItem(LEGACY_OPT_IN_KEY) === "1") {
		apply_custom_theme();
	}

	const original_fetch_themes = frappe.ui.ThemeSwitcher.prototype.fetch_themes;
	frappe.ui.ThemeSwitcher.prototype.fetch_themes = function () {
		return original_fetch_themes.call(this).then((themes) => {
			themes.push({
				name: "custom",
				label: __("Custom"),
				info: __("This app's custom violet theme"),
			});
			return themes;
		});
	};

	const original_toggle_theme = frappe.ui.ThemeSwitcher.prototype.toggle_theme;
	frappe.ui.ThemeSwitcher.prototype.toggle_theme = function (theme) {
		if (theme === "custom") {
			localStorage.removeItem(OPT_OUT_KEY);
			localStorage.removeItem(LEGACY_OPT_IN_KEY);
			this.current_theme = "custom";
			apply_custom_theme();
			frappe.show_alert(__("Theme Changed"), 3);
			return;
		}
		localStorage.setItem(OPT_OUT_KEY, "1");
		localStorage.removeItem(LEGACY_OPT_IN_KEY);
		return original_toggle_theme.call(this, theme);
	};
})();

// The sidebar header's "Desktop" menu item calls frappe.set_route("/desk"),
// which — when triggered as an in-app SPA navigation (not a fresh page load)
// — re-enters the already-instantiated Workspace page's own fallback
// (get_page_to_show()), which prefers whatever workspace localStorage
// remembers as "last visited" over Home, and also skips updating the URL to
// the resolved workspace's slug since the route segment is already non-empty
// by the time it checks. Net effect: clicking "Desktop" inconsistently lands
// on whatever was last viewed, with the URL staying at bare /desk instead of
// /desk/home. Routing straight to "home" sidesteps both problems.
(function () {
	const OriginalSidebarHeader = frappe.ui.SidebarHeader;
	frappe.ui.SidebarHeader = class extends OriginalSidebarHeader {
		constructor(sidebar) {
			super(sidebar);
			// sidebar.js's setup() calls `new SidebarHeader(...)` before it renders
			// the sidebar body and doesn't wrap the call in try/catch, so an error
			// here would silently blank the whole sidebar — never let this throw.
			try {
				const desktop_item = this.dropdown_items.find((item) => item.name === "desktop");
				if (desktop_item) {
					desktop_item.onClick = function () {
						frappe.route_flags.replace_route = true;
						frappe.set_route("home");
					};
				}

				// This app's own "Website" sidebar section (hidden via
				// customize_sidebar.hide_modules) already covers Web Page/Web
				// Form/etc for HRMS-only deployments; this dropdown item is a
				// separate, hardcoded stock entry that just opens the public
				// site root and isn't reachable from that script.
				this.dropdown_items = this.dropdown_items.filter((item) => item.name !== "website");
			} catch (e) {
				console.error(e);
			}
		}
	};
})();

// The breadcrumb "home" icon (top-left, before "/ <workspace>") links to
// bare /desk — the exact same frappe.set_route("/desk") bug as the "Desktop"
// menu item above: as an in-app SPA navigation it re-enters Workspace's own
// fallback (get_page_to_show()), landing on whatever workspace localStorage
// remembers as "last visited" (e.g. Stock) instead of Home, surfacing that
// workspace's own onboarding panel. frappe.breadcrumbs.clear() rebuilds this
// link from scratch on every route change, so intercept its click there each
// time rather than patching a single element once.
(function () {
	const original_clear = frappe.breadcrumbs.clear;
	frappe.breadcrumbs.clear = function () {
		original_clear.call(this);
		this.$breadcrumbs.find('a[href="/desk"]').on("click", function (e) {
			e.preventDefault();
			frappe.route_flags.replace_route = true;
			frappe.set_route("home");
		});
	};
})();

// One-time cleanup: while reviewing the newly-merged "Home" sidebar (40+
// module sections, all meant to start collapsed via keep_closed), a few
// sections got expanded by hand — Frappe remembers per-section open/closed
// state in localStorage("section-breaks-state") keyed by workspace, and that
// remembered state overrides keep_closed on every future load, including hard
// refresh. Clear just the "home" entry once so every section goes back to its
// intended collapsed default; ordinary future clicks will persist normally
// again afterward.
(function () {
	const RESET_MARKER = "india_payroll_home_sidebar_state_reset_v1";
	if (localStorage.getItem(RESET_MARKER)) return;

	try {
		const raw = localStorage.getItem("section-breaks-state");
		if (raw) {
			const state = JSON.parse(raw);
			if (state && typeof state === "object" && "home" in state) {
				delete state.home;
				localStorage.setItem("section-breaks-state", JSON.stringify(state));
			}
		}
	} catch (e) {
		console.error(e);
	}

	localStorage.setItem(RESET_MARKER, "1");
})();

// Sidebar header subtitle ("Home" / "ERPNext") is resolved dynamically —
// Sidebar.choose_app_name() matches the current workspace's module back to
// whichever installed app owns it (via Module Def.app_name), and for the
// merged Home sidebar that still resolves to ERPNext, since Home's own
// module has always belonged to it. Rather than rewire that module/app
// ownership chain, call the original (so frappe.current_app and sibling-icon
// lookups elsewhere still work) and just brand the visible label afterward.
(function () {
	const original_choose_app_name = frappe.ui.Sidebar.prototype.choose_app_name;
	frappe.ui.Sidebar.prototype.choose_app_name = function () {
		original_choose_app_name.call(this);
		this.header_subtitle = "Pratyin HRMS";
	};
})();

// Module (Section Break) rows in the sidebar carry an `icon` field in the
// database — every merged module here has one set — but sidebar_item.html's
// Section Break branch only ever renders the label, never the icon, unlike
// the Link-item branch just below it. Rather than fork that compiled
// template, append the icon markup onto the already-rendered row afterward.
(function () {
	const original_make = frappe.ui.sidebar_item.TypeSectionBreak.prototype.make;
	frappe.ui.sidebar_item.TypeSectionBreak.prototype.make = function () {
		original_make.call(this);
		if (!this.wrapper || !this.item.icon) return;

		const $section_break = this.wrapper.find(".item-anchor.section-break");
		if (!$section_break.length || $section_break.find(".sidebar-item-icon").length) return;

		const icon_html = frappe.utils.icon(this.item.icon, "sm", "", "", "text-ink-gray-7 current-color", true);
		$(`<span class="sidebar-item-icon" item-icon="${this.item.icon}">${icon_html}</span>`).prependTo(
			$section_break
		);
	};
})();

// Collapsed sidebar rail: stock Frappe hides every module section header and
// force-opens its children into one flat icon column once the sidebar
// collapses — fine for a handful of items, unworkable at this app's scale
// (645 items across 39 merged module sections, several 40-60+ items deep).
// Keep only the module-level icon visible when collapsed (now that the fix
// above gives every section header one), keep its children closed, and show
// them in a hover flyout instead of flattening into the icon column.
// Standalone top-level items with no nested_items (Shortcuts, Automation,
// ...) are untouched — they still click straight through as before.
(function () {
	const FLYOUT_CLASS = "india-payroll-sidebar-flyout";
	let $flyout = null;
	let hide_timer = null;

	function clear_hide_timer() {
		if (hide_timer) {
			clearTimeout(hide_timer);
			hide_timer = null;
		}
	}

	function hide_flyout() {
		clear_hide_timer();
		if ($flyout) {
			$flyout.remove();
			$flyout = null;
		}
	}

	function schedule_hide_flyout() {
		clear_hide_timer();
		hide_timer = setTimeout(hide_flyout, 200);
	}

	function show_flyout(anchor_el, nested_items) {
		hide_flyout();
		if (!anchor_el || !nested_items || !nested_items.length) return;

		$flyout = $(`<div class="${FLYOUT_CLASS}"></div>`).appendTo("body");
		$flyout.on("mouseenter", clear_hide_timer);
		$flyout.on("mouseleave", schedule_hide_flyout);

		const $list = $(`<div class="${FLYOUT_CLASS}-list"></div>`).appendTo($flyout);
		nested_items.forEach((item) => {
			frappe.app.sidebar.make_sidebar_item({ container: $list, item });
		});
		$list.find("a.item-anchor").on("click", hide_flyout);

		const rect = anchor_el.getBoundingClientRect();
		const is_rtl = frappe.utils.is_rtl();
		$flyout.css({
			position: "fixed",
			[is_rtl ? "right" : "left"]: rect.right + 6 + "px",
			top: rect.top + "px",
		});
		// re-clamp against the viewport bottom now that content is in and
		// outerHeight() is measurable (it was 0 pre-append)
		const max_top = window.innerHeight - $flyout.outerHeight() - 8;
		$flyout.css("top", Math.max(8, Math.min(rect.top, max_top)) + "px");
	}

	const original_make = frappe.ui.sidebar_item.TypeSectionBreak.prototype.make;
	frappe.ui.sidebar_item.TypeSectionBreak.prototype.make = function () {
		original_make.call(this);
		if (!this.wrapper || !this.nested_items || !this.nested_items.length) return;

		const me = this;
		this.wrapper.on("mouseenter", function () {
			if (frappe.app.sidebar.sidebar_expanded) return;
			clear_hide_timer();
			show_flyout(me.wrapper.find(".item-anchor.section-break")[0], me.nested_items);
		});
		this.wrapper.on("mouseleave", schedule_hide_flyout);
	};

	// Replaces (not wraps) the stock listener: the stock version hides
	// .section-break entirely on collapse and force-opens children via
	// me.open() — both of which this fix intentionally undoes. The
	// expanding branch is left functionally identical to stock.
	frappe.ui.sidebar_item.TypeSectionBreak.prototype.toggle_on_collapse = function () {
		const me = this;
		this.old_state;
		$(document).on("sidebar-expand", function (event, expand) {
			if (expand.sidebar_expand) {
				$(me.wrapper.find(".section-break")).removeClass("hidden");
				$(me.wrapper.find(".divider")).addClass("hidden");
				if (me.old_state !== undefined) {
					me.collapsed = me.old_state;
					me.toggle();
				}
			} else {
				hide_flyout();
				$(me.wrapper.find(".divider")).addClass("hidden");
				me.old_state = me.collapsed;
				me.close();
			}
		});
	};
})();

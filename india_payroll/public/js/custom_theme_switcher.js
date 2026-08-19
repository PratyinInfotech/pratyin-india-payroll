// Adds a fourth "Custom" option to the built-in Switch Theme dialog (alongside
// Frappe Light / Timeless Night / Automatic) without touching the three stock
// themes. Selection is remembered in localStorage rather than the User's
// `desk_theme` field, since that field's options and the server-side
// `switch_theme` whitelist only accept Light/Dark/Automatic.
(function () {
	const STORAGE_KEY = "india_payroll_custom_theme_enabled";

	function apply_custom_theme() {
		document.documentElement.setAttribute("data-theme-mode", "custom");
		document.documentElement.setAttribute("data-theme", "custom");
	}

	if (localStorage.getItem(STORAGE_KEY) === "1") {
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
			localStorage.setItem(STORAGE_KEY, "1");
			this.current_theme = "custom";
			apply_custom_theme();
			frappe.show_alert(__("Theme Changed"), 3);
			return;
		}
		localStorage.removeItem(STORAGE_KEY);
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

/**
 * Pratyin branding for the desk's About dialog.
 *
 * frappe's own dialog (frappe/public/js/frappe/ui/toolbar/about.js) leads with
 * the Frappe wordmark, links out to frappe.io / github.com/frappe /
 * discuss.frappe.io, states the Frappe Framework version, lists every
 * installed app with its version, and closes with the Frappe Technologies
 * copyright. On a white-labelled deployment that is the one dialog that
 * undoes the branding everywhere else.
 *
 * frappe is pinned to an upstream tag here, so it is not edited in place.
 * `frappe.ui.misc.about` is a plain function on a namespace and this file is
 * loaded through app_include_js, i.e. after the desk bundle, so reassigning it
 * is enough -- and it survives bench update because nothing in frappe is
 * touched. frappe.ui.toolbar.show_about() calls through to this.
 */
frappe.provide("frappe.ui.misc");

const PRATYIN_BRAND_NAME = "Pratyin HR";
const PRATYIN_BRAND_LOGO = "/assets/india_payroll/images/pratyin-logo.png";

frappe.ui.misc.about = function () {
	// frappe caches its dialog on the same key. Reuse ours the same way so
	// reopening About does not build a second one.
	if (frappe.ui.misc.about_dialog) {
		frappe.ui.misc.about_dialog.show();
		return;
	}

	const dialog = new frappe.ui.Dialog({ title: __("About") });
	$(dialog.wrapper).addClass("about-dialog pratyin-about-dialog");

	$(dialog.body).html(`
		<div class="pratyin-about-body">
			<img
				src="${PRATYIN_BRAND_LOGO}"
				alt="${frappe.utils.escape_html(PRATYIN_BRAND_NAME)}"
				class="pratyin-about-logo"
			>
			<div class="pratyin-about-name">${frappe.utils.escape_html(PRATYIN_BRAND_NAME)}</div>
		</div>
	`);

	// frappe's dialog un-hides its footer to hang the copyright line on it.
	// Ours has nothing to put there, so the footer stays hidden.

	frappe.ui.misc.about_dialog = dialog;
	frappe.ui.misc.about_dialog.show();
};

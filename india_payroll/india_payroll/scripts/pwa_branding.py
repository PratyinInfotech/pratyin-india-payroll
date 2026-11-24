"""Rebrand the Frappe HR mobile portal (``/hrms``) as Pratyin HR.

The portal is a Vue PWA that ships inside the ``hrms`` app. Its visible name
reaches the screen two different ways, so rebranding takes two mechanisms:

* Markup the server controls — the document title, the iOS web-app title, the
  manifest and the icon set — is handled by ``india_payroll/www/hrms.html``,
  which shadows ``hrms/www/hrms.html`` because Frappe resolves ``www`` pages
  over ``reversed(frappe.get_installed_apps())`` and india_payroll installs
  last.

* Strings baked into the compiled Vue bundle — "Install Frappe HR" on the
  install prompt, "Login to Frappe HR" on the sign-in screen and the "Frappe
  HR" header — are passed through the frontend's ``__()`` helper. That helper
  reads ``frappe.boot.__messages``, which ``frappe.translate.get_all_translations``
  builds by layering Translation records *over* the apps' own catalogues. So a
  Translation row per string retargets them without forking hrms or rebuilding
  its bundle, and it survives ``bench update``.

Seeded from both ``after_install`` and ``after_migrate`` so a fresh site and an
existing one converge on the same state.
"""

import frappe
import frappe.translate

# Site language. The rows only apply to users actually browsing in this
# language; English is what this deployment runs on.
LANGUAGE = "en"

# Source string -> replacement. Keys must match the msgid in the hrms bundle
# character for character, otherwise __() falls through to the original.
BRAND_TRANSLATIONS = {
	"Frappe HR": "Pratyin HR",
	"Install Frappe HR": "Install Pratyin HR",
	"Login to Frappe HR": "Login to Pratyin HR",
}


def apply_brand_translations():
	"""Create or correct the Translation rows that rename Frappe HR."""
	changed = False

	for source_text, translated_text in BRAND_TRANSLATIONS.items():
		existing = frappe.db.get_value(
			"Translation",
			{"language": LANGUAGE, "source_text": source_text},
			["name", "translated_text"],
			as_dict=True,
		)

		if existing:
			if existing.translated_text == translated_text:
				continue
			# Someone edited the row, or the wording changed here. Realign it
			# rather than inserting a duplicate.
			frappe.db.set_value("Translation", existing.name, "translated_text", translated_text)
			changed = True
			continue

		doc = frappe.new_doc("Translation")
		doc.language = LANGUAGE
		doc.source_text = source_text
		doc.translated_text = translated_text
		doc.insert(ignore_permissions=True)
		changed = True

	if changed:
		# get_user_translations and the merged catalogue are both cached per
		# language and read at boot, so without this the rename would only
		# surface after the next unrelated cache eviction.
		frappe.translate.clear_cache()

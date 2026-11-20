import frappe

# User records to keep out of the User list view, Link-field dropdowns and
# report views -- for EVERY user, Administrator included.
#
# Frappe already hides both STANDARD_USERS ("Guest", "Administrator") from
# everyone except Administrator, in
# frappe/core/doctype/user/user.py :: get_permission_query_conditions, which
# returns "" (no filter at all) when the caller is Administrator. That
# exemption is why Guest is still visible while signed in as Administrator.
# This hook adds a second condition that has no such exemption.
#
# Frappe collects EVERY app's permission_query_conditions hook for a doctype
# and joins them with " and " (frappe/model/db_query.py ::
# get_permission_query_conditions), so this narrows frappe's own rule rather
# than replacing it -- a non-Administrator still cannot see Administrator.
#
# Scope, deliberately: this filters permission-checked QUERIES only
# (frappe.get_list / reportview / link search). It does NOT touch
# frappe.db.get_value, frappe.get_doc, frappe.get_cached_value or anything
# passing ignore_permissions=True, which is exactly why hiding Guest is safe:
# the login page's own lookup of the Guest row
# (frappe/www/login.py :: get_context -> db.get_value("User", "Guest", ...))
# and session validation (frappe/sessions.py :: validate_user) both bypass
# this and keep working. The row is untouched; only its visibility changes.
#
# Administrator is intentionally NOT listed -- hiding it would remove it from
# its own list view while signed in as Administrator, which is confusing and
# hides a real account that an admin may legitimately need to edit.
HIDDEN_USERS = ("Guest",)


def user_query_conditions(user=None, doctype=None):
	"""permission_query_conditions hook for the User doctype."""
	if not HIDDEN_USERS:
		return ""

	names = ", ".join(frappe.db.escape(name) for name in HIDDEN_USERS)
	return f"(`tabUser`.name not in ({names}))"

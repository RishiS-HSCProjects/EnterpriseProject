from flask import flash as flask_flash, session
from html import escape
from datetime import date, time


def serialize_form_data(form):
    """Serialize form data to dictionary for session storage.

    Converts all form field data to a dict, handling date/time as ISO strings.

    Args:
        form: Flask-WTF form instance.

    Returns:
        Dictionary of field names to values.
    """
    data = {}
    for field in form:
        if hasattr(field, 'data'):
            value = field.data
            if isinstance(value, (date, time)):
                data[field.name] = value.isoformat()
            else:
                data[field.name] = value
    return data


def serialize_form_errors(form):
    """Serialize form errors to dictionary for session storage.

    Args:
        form: Flask-WTF form instance.

    Returns:
        Dictionary of field names to error lists.
    """
    error_dict = {}
    for field_name, error_list in form.errors.items():
        error_dict[field_name] = error_list
    return error_dict


def _repopulate_form(form, form_data=None, form_errors=None):
    """Repopulate form with serialized data and errors from session.

    Args:
        form: Flask-WTF form instance to populate.
        form_data: Dict of field data from serialize_form_data.
        form_errors: Dict of field errors from serialize_form_errors.

    Returns:
        Repopulated form instance.
    """
    form_data = form_data or {}
    form_errors = form_errors or {}

    # Restore form data
    for field_name, value in form_data.items():
        if not hasattr(form, field_name):
            continue
        field = getattr(form, field_name)
        if isinstance(value, str):
            if field_name == 'date':
                try:
                    field.data = date.fromisoformat(value)
                except (ValueError, TypeError):
                    pass
            elif field_name in ['start_time', 'end_time']:
                try:
                    field.data = time.fromisoformat(value)
                except (ValueError, TypeError):
                    pass
            else:
                field.data = value
        else:
            field.data = value

    # Restore form errors
    for field_name, errors in form_errors.items():
        if hasattr(form, field_name):
            getattr(form, field_name).errors = errors

    return form


def save_form_state(form, form_id, prefix=''):
    """Save form data and errors to session.

    Use this after form validation fails to preserve state across redirect.

    Args:
        form: Flask-WTF form instance.
        form_id: Identifier for which form this is (e.g., 'login_form').
        prefix: Optional prefix for session key (e.g., 'login_' → 'login_form_state').
    """
    state_key = f'{prefix}form_state'
    session[state_key] = {
        'form_id': form_id,
        'form_data': serialize_form_data(form),
        'form_errors': serialize_form_errors(form),
    }


def restore_form_state(form, prefix=''):
    """Restore form data and errors from session (one-time).

    Automatically pops form state from session, so it only displays once.

    Args:
        form: Flask-WTF form instance to populate.
        prefix: Optional prefix for session key.

    Returns:
        Repopulated form if state existed, otherwise unchanged form.
    """
    state_key = f'{prefix}form_state'
    form_state = session.pop(state_key, {})

    if form_state:
        form_data = form_state.get('form_data', {})
        form_errors = form_state.get('form_errors', {})

        # Flash errors to user
        if form_errors:
            flash_form_errors(form, form_errors)

        # Repopulate form
        form = _repopulate_form(form, form_data, form_errors)

    return form


def flash_form_errors(form, form_errors=None):
    """Flash form errors (either from form or from dict).

    Args:
        form: Flask-WTF form instance (for field labels).
        form_errors: Optional dict of errors from serialize_form_errors.
    """
    errors_to_flash = form_errors if form_errors else form.errors

    for field_name, error_list in errors_to_flash.items():
        field = getattr(form, field_name, None)
        if field and hasattr(field, 'label'):
            field_label = field.label.text
        else:
            field_label = field_name.replace('_', ' ').title()

        for error in error_list:
            safe_error = escape(str(error), quote=False)
            flash(f"{field_label}: {safe_error}", 'error')


def flash_all_form_errors(form) -> None:
    """Flash all form validation errors.

    This function iterates through all form fields and flashes
    any validation errors associated with them.

    Args:
        form: Flask-WTF form instance with potential validation errors.
    """
    if form.errors:
        for field_name, errors in form.errors.items():
            field = getattr(form, field_name, None)
            field_label = getattr(field, 'label', None)

            if 'csrf_token' in field_name.lower():
                flash("Your session has expired. Please try again.", 'error')
                continue

            if field_label:
                label_text = field_label.text
            else:
                label_text = field_name.replace('_', ' ').title()

            for error in errors:
                safe_error = escape(str(error), quote=False)
                flash(f"{label_text}: {safe_error}", 'error')


def flash(message: str, category: str = 'info') -> None:
    """Flash a message with custom category.

    Args:
        message: The message to display.
        category: The category for styling ('success', 'error', 'warning', 'info').
    """
    valid_categories = {'success', 'error', 'warning', 'info'}
    if category not in valid_categories:
        category = 'info'
    # Prevent exact duplicate flashes in the same session (helps avoid repeated form flashes)
    try:
        existing = session.get('_flashes', [])
    except Exception:
        existing = []

    # Flask stores flashes as (category, message) tuples in session['_flashes']
    if any(flash_item == (category, message) for flash_item in existing):
        return

    flask_flash(message, category)

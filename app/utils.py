from flask import flash as flask_flash
from html import escape


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
            
            if field_label:
                label_text = field_label.text
            else:
                label_text = field_name.replace('_', ' ').title()
            
            for error in errors:
                safe_error = escape(str(error))
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
    
    flask_flash(message, category)

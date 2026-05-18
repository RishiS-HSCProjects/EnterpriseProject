from functools import wraps
from flask import Blueprint, current_app, redirect, render_template, url_for
from flask_login import current_user, login_required
from app import db
from app.forms import BlockedIpAddForm, EmptyForm, WhitelistAddForm
from app.models.otp_log import BlockedIp
from app.models.user import UserNotFound
from app.models.whitelist import PermissionDenied, UserAlreadyWhitelisted, Whitelist
from app.utils.utils import flash, flash_all_form_errors

admin_bp = Blueprint(
	'admin',
	__name__,
	url_prefix='/admin',
	template_folder='templates',
	static_folder='static',
	static_url_path='/admin/static',
)

def admin_required(view): # Wrapper function
	"""Require an authenticated admin before entering an admin route."""
	@wraps(view)
	@login_required
	def wrapped(*args, **kwargs):
		if not current_user.is_admin():
			flash('Access denied: Admins only.', 'error')
			return redirect(url_for('main.dashboard'))

		return view(*args, **kwargs)

	return wrapped

@admin_bp.route('/')
@admin_required
def panel():
	whitelist_entries = Whitelist.query.order_by(Whitelist.whitelisted_at.desc()).all()
	# Exclude current user's own entry from display
	visible_entries = [entry for entry in whitelist_entries if entry.xuid != current_user.xuid]
	blocked_ips = BlockedIp.query.order_by(BlockedIp.blocked_at.desc()).all()

	return render_template(
		'admin.html',
		add_form=WhitelistAddForm(),
		remove_form=EmptyForm(),
		whitelist_entries=visible_entries,
		blocked_ip_form=BlockedIpAddForm(),
		blocked_ips=blocked_ips,
	)

@admin_bp.route('/whitelist/add', methods=['POST'])
@admin_required
def whitelist_add():
	form = WhitelistAddForm()
	if not form.validate_on_submit():
		flash_all_form_errors(form)
		return redirect(url_for('admin.panel'))

	username = (form.username.data or '').strip()

	try:
		whitelist_entry = Whitelist.whitelist_user(username)
		db.session.add(whitelist_entry)
		db.session.commit()
		flash(f'{username} was added to the whitelist.', 'success')
	except (UserAlreadyWhitelisted, PermissionDenied, UserNotFound) as exc:
		db.session.rollback()
		flash(str(exc), 'error')
	except Exception as exc:
		db.session.rollback()
		current_app.logger.error(f'Unexpected whitelist add error: {exc}')
		flash('An unexpected error occurred while adding this user.', 'error')

	return redirect(url_for('admin.panel'))

@admin_bp.route('/whitelist/remove/<int:entry_id>', methods=['POST'])
@admin_required
def whitelist_remove(entry_id: int):
	form = EmptyForm()
	if not form.validate_on_submit():
		flash('Invalid request. Please refresh the page and try again.', 'error')
		return redirect(url_for('admin.panel'))

	whitelist_entry = Whitelist.query.get_or_404(entry_id)
	username = whitelist_entry.username

	if whitelist_entry.xuid == current_user.xuid:
		flash('You cannot remove your own whitelist entry.', 'error')
		return redirect(url_for('admin.panel'))
	
	if whitelist_entry.get_user() and whitelist_entry.get_user().is_admin():
		flash('You cannot remove a whitelist entry for another admin.', 'error')
		return redirect(url_for('admin.panel'))

	try:
		whitelist_entry.unwhitelist()
		db.session.commit()
		flash(f'{username} was removed from the whitelist.', 'success')
	except Exception as exc:
		db.session.rollback()
		current_app.logger.error(f'Unexpected whitelist remove error: {exc}')
		flash('An unexpected error occurred while removing this user.', 'error')

	return redirect(url_for('admin.panel'))

@admin_bp.route('/blocked-ip/add', methods=['POST'])
@admin_required
def blocked_ip_add():
	form = BlockedIpAddForm()
	if not form.validate_on_submit():
		flash_all_form_errors(form)
		return redirect(url_for('admin.panel'))

	ip_address = (form.ip_address.data or '').strip()

	existing = BlockedIp.query.filter_by(ip_address=ip_address).first()
	if existing:
		flash(f'{ip_address} is already blocked.', 'error')
		return redirect(url_for('admin.panel'))

	try:
		blocked_ip = BlockedIp()
		blocked_ip.ip_address = ip_address
		db.session.add(blocked_ip)
		db.session.commit()
		flash(f'{ip_address} has been blocked.', 'success')
	except Exception as exc:
		db.session.rollback()
		current_app.logger.error(f'Unexpected blocked IP add error: {exc}')
		flash('An unexpected error occurred while blocking this IP.', 'error')

	return redirect(url_for('admin.panel'))

@admin_bp.route('/blocked-ip/remove/<int:ip_id>', methods=['POST'])
@admin_required
def blocked_ip_remove(ip_id: int):
	form = EmptyForm()
	if not form.validate_on_submit():
		flash('Invalid request. Please refresh the page and try again.', 'error')
		return redirect(url_for('admin.panel'))

	blocked_ip = BlockedIp.query.get_or_404(ip_id)
	ip_address = blocked_ip.ip_address

	try:
		db.session.delete(blocked_ip)
		db.session.commit()
		flash(f'{ip_address} has been unblocked.', 'success')
	except Exception as exc:
		db.session.rollback()
		current_app.logger.error(f'Unexpected blocked IP remove error: {exc}')
		flash('An unexpected error occurred while unblocking this IP.', 'error')

	return redirect(url_for('admin.panel'))

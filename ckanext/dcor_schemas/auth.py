import ckan.authz as authz
from ckan import logic
import ckan.plugins.toolkit as toolkit

from . import helpers as dcor_helpers


def dataset_purge(context, data_dict):
    """Only allow deletion of deleted datasets"""
    # user must be logged-in
    ac = login_user(context)
    if not ac["success"]:
        return ac
    # original auth function
    # (usually, only sysadmins are allowed to purge, so we test against
    # package_update)
    ao = logic.auth.update.package_update(context, data_dict)
    if not ao["success"]:
        return ao

    # get the current package dict
    show_context = {
        'model': context['model'],
        'session': context['session'],
        'user': context['user'],
        'auth_user_obj': context['auth_user_obj'],
    }
    package_dict = logic.get_action('package_show')(
        show_context,
        {'id': logic.get_or_bust(data_dict, 'id')})
    state = package_dict.get('state')
    if state != "deleted":
        return {"success": False,
                "msg": "Only deleted datasets can be purged!"}
    return {"success": True}


def deny(context, data_dict):
    return {'success': False,
            'msg': "Only admins may do so."}


def login_user(context, data_dict=None):
    # Get the user name of the logged-in user.
    user = context['user']
    convert_user_name_or_id_to_id = toolkit.get_converter(
        'convert_user_name_or_id_to_id')
    try:
        # check whether the user is logged-in
        convert_user_name_or_id_to_id(user, context)
    except toolkit.Invalid:
        # The user doesn't exist (e.g. they're not logged-in).
        return {'success': False,
                'msg': 'You must be logged-in.'}

    # All users are allowed to do this
    return {'success': True}


def package_create(context, data_dict):
    # user must be logged-in
    ac = login_user(context)
    if not ac["success"]:
        return ac

    user = context['user']
    # If a group is given, check whether the user has the necessary permissions
    check_group = logic.auth.create._check_group_auth(context, data_dict)
    if not check_group:
        return {'success': False,
                'msg': 'User {} not authorized to edit '.format(user)
                       + 'these collections'}

    # Are we allowed to add a dataset to the given organization?
    org_id = data_dict.get('owner_org', None)
    if org_id is None:
        # No organization was given. This means that we just have to check
        # whether the user can create packages in general. Since the user
        # is logged-in, he can do that.
        pass
    else:
        if not authz.has_user_permission_for_group_or_org(
                org_id, user, 'create_dataset'):
            return {'success': False,
                    'msg': 'User {} not authorized to add '.format(user)
                           + 'datasets to circle {}!'.format(org_id)}

    return {"success": True}


def package_delete(context, data_dict):
    """Only allow deletion of draft datasets"""
    # user must be logged-in
    ac = login_user(context)
    if not ac["success"]:
        return ac
    # original auth function
    ao = logic.auth.update.package_update(context, data_dict)
    if not ao["success"]:
        return ao

    # get the current package dict
    show_context = {
        'model': context['model'],
        'session': context['session'],
        'user': context['user'],
        'auth_user_obj': context['auth_user_obj'],
    }
    package_dict = logic.get_action('package_show')(
        show_context,
        {'id': logic.get_or_bust(data_dict, 'id')})
    state = package_dict.get('state')
    if state != "draft":
        return {"success": False,
                "msg": "Only draft datasets can be deleted!"}
    return {"success": True}


def package_update(context, data_dict=None):
    # user must be logged-in
    ac = login_user(context)
    if not ac["success"]:
        return ac
    # original auth function
    ao = logic.auth.update.package_update(context, data_dict)
    if not ao["success"]:
        return ao

    # get the current package dict
    show_context = {
        'model': context['model'],
        'session': context['session'],
        'user': context['user'],
        'auth_user_obj': context['auth_user_obj'],
    }
    package_dict = logic.get_action('package_show')(
        show_context,
        {'id': logic.get_or_bust(data_dict, 'id')})
    # do not allow switching to a more restrictive license
    if "license_id" in data_dict:
        allowed = dcor_helpers.get_valid_licenses(package_dict["license_id"])
        if data_dict["license_id"] not in allowed:
            return {'success': False,
                    'msg': 'Cannot switch to more-restrictive license'}
    # do not allow setting state from "active" to "draft"
    if package_dict["state"] != "draft" and data_dict.get("state") == "draft":
        return {'success': False,
                'msg': 'Changing dataset state to draft not allowed'}
    # do not allow setting the visibility from public to private
    if not package_dict["private"] and data_dict.get("private", False):
        return {'success': False,
                'msg': 'Changing visibility to private not allowed'}
    # do not allow changing some of the keys
    prohibited_keys = ["name"]
    invalid = {}
    for key in data_dict:
        if (key in package_dict
            and key in prohibited_keys
                and data_dict[key] != package_dict[key]):
            invalid[key] = data_dict[key]
    if invalid:
        return {'success': False,
                'msg': 'Editing not allowed: {}'.format(invalid)}

    return {'success': True}


def resource_create(context, data_dict=None):
    # user must be logged-in
    ac = login_user(context)
    if not ac["success"]:
        return ac
    # original auth function
    ao = logic.auth.create.resource_create(context, data_dict)
    if not ao["success"]:
        return ao

    if "package_id" in data_dict:
        pkg_dict = logic.get_action('package_show')(
            dict(context, return_type='dict'),
            {'id': data_dict["package_id"]})

        # do not allow adding resources to non-draft datasets
        if pkg_dict["state"] != "draft":
            return {'success': False,
                    'msg': 'Adding resources to non-draft datasets not '
                           'allowed!'}

        if "upload" in data_dict:
            # id must not be set
            if data_dict.get("id", ""):
                return {'success': False,
                        'msg': 'You are not allowed to set the id!'}

    return {'success': True}


def resource_update(context, data_dict=None):
    # user must be logged-in
    ac = login_user(context)
    if not ac["success"]:
        return ac
    # original auth function
    ao = logic.auth.update.resource_update(context, data_dict)
    if not ao["success"]:
        return ao

    # get the current resource dict
    show_context = {
        'model': context['model'],
        'session': context['session'],
        'user': context['user'],
        'auth_user_obj': context['auth_user_obj'],
    }
    resource_dict = logic.get_action('resource_show')(
        show_context,
        {'id': logic.get_or_bust(data_dict, 'id')})
    # convert to package id (otherwise the check below might fail)
    convert_package_name_or_id_to_id = toolkit.get_converter(
        'convert_package_name_or_id_to_id')
    data_dict["package_id"] = convert_package_name_or_id_to_id(
            logic.get_or_bust(data_dict, "package_id"), context)
    # only allow updating the description
    allowed_keys = ["description"]
    invalid = {}
    for key in data_dict:
        if (key not in resource_dict
            or (key not in allowed_keys
                and data_dict[key] != resource_dict[key])):
            invalid[key] = data_dict[key]
    if invalid:
        return {'success': False,
                'msg': 'Editing not allowed: {}'.format(invalid)}

    return {'success': True}

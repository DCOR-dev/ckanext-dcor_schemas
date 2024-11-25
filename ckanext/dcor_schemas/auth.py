from email.utils import parseaddr
import re

from ckan.common import asbool, config
from ckan import authz, logic
import ckan.plugins.toolkit as toolkit
from dcor_shared import get_ckan_config_option, s3

from . import helpers as dcor_helpers
from . import resource_schema_supplements as rss


@logic.auth_allow_anonymous_access
def content_listing(context, data_dict):
    """manage access for listing all circles, groups, tags"""
    if not asbool(config.get(
            "ckanext.dcor_schemas.allow_content_listing_for_anon", "true")):
        return logic.auth.restrict_anon(context)
    else:
        return {'success': True}


def dataset_purge(context, data_dict):
    """Only allow deletion of deleted datasets"""
    # original auth function
    # (usually, only sysadmins are allowed to purge, so we test against
    # package_update)
    aut = logic.auth.update.package_update(context, data_dict)
    if not aut["success"]:
        return aut

    # get the current package dict
    show_context = {
        'model': context['model'],
        'session': context['session'],
        'user': context['user'],
        'auth_user_obj': context['auth_user_obj'],
    }
    pkg_dict = logic.get_action('package_show')(
        show_context,
        {'id': get_package_id(context, data_dict)})
    state = pkg_dict.get('state')
    if state != "deleted":
        return {"success": False,
                "msg": "Only deleted datasets can be purged!"}
    return {"success": True}


def deny(context, data_dict):
    return {'success': False,
            'msg': "Only admins may do so."}


def get_package_id(context, data_dict):
    """Convenience function that extracts the package_id"""
    package = context.get('package')
    if package:
        # web
        package_id = package.id
    else:
        package_id = logic.get_or_bust(data_dict, 'id')
    convert_package_name_or_id_to_id = toolkit.get_converter(
        'convert_package_name_or_id_to_id')
    return convert_package_name_or_id_to_id(package_id, context)


def package_create(context, data_dict):
    # Note that we did not decorate this function with
    # @logic.auth_allow_anonymous_access. This effectively
    # disables dataset creation via the web interface.
    # However, we make sure that the API is used with the following:
    using_api = 'api_version' in context
    if not using_api:
        return {"success": False,
                "msg": "Creating datasets is only possible via the API. "
                       "Please use DCOR-Aid for uploading data!"}

    # original auth function
    aut = logic.auth.create.package_create(context, data_dict)
    if not aut["success"]:
        return aut

    if data_dict:
        # A regular user is not allowed to specify the dataset ID
        if data_dict.get("id"):
            return {"success": False,
                    "msg": "Only sysadmins may specify a dataset ID"}

        # Use our own configuration option to determine whether the
        # admin has disabled public datasets (e.g. for DCOR-med).
        must_be_private = not asbool(config.get(
            "ckanext.dcor_schemas.allow_public_datasets", "true"))
        private_default = must_be_private  # public if not has to be private
        is_private = asbool(data_dict.get('private', private_default))
        if must_be_private and not is_private:
            return {"success": False,
                    "msg": "Creating public datasets has been disabled via "
                           "the configuration option 'ckanext.dcor_schemas."
                           "allow_public_datasets = false'!"}

    return {"success": True}


def package_delete(context, data_dict):
    """Only allow deletion of draft datasets"""
    # original auth function
    aut = logic.auth.update.package_update(context, data_dict)
    if not aut["success"]:
        return aut

    # get the current package dict
    show_context = {
        'model': context['model'],
        'session': context['session'],
        'user': context['user'],
        'auth_user_obj': context['auth_user_obj'],
    }
    pkg_dict = logic.get_action('package_show')(
        show_context,
        {'id': get_package_id(context, data_dict)})
    state = pkg_dict.get('state')
    if state != "draft":
        return {"success": False,
                "msg": "Only draft datasets can be deleted!"}
    return {"success": True}


def package_update(context, data_dict=None):
    # original auth function
    aut = logic.auth.update.package_update(context, data_dict)
    if not aut["success"]:
        return aut

    if data_dict is None:
        data_dict = {}

    # get the current package dict
    show_context = {
        'model': context['model'],
        'session': context['session'],
        'user': context['user'],
        'auth_user_obj': context['auth_user_obj'],
    }
    ds_dict = logic.get_action('package_show')(
        show_context,
        {'id': get_package_id(context, data_dict)})
    resources_exist = ds_dict["resources"]

    # run resource check functions
    for ii, new_res in enumerate(data_dict.get("resources", [])):
        position = new_res.get("position")
        if (position is not None
                and position == ii
                and len(resources_exist) > position
                and new_res == resources_exist[position]):
            # We do not need to verify things that haven't changed.
            continue

        # Find the resource in the current dataset.
        cur_res = None
        if "id" in new_res:
            for res in resources_exist:
                if res["id"] == new_res["id"]:
                    cur_res = res
                    break

        # Note that on DCOR, you are not allowed to specify the ID
        # during upload, unless the resource was already uploaded to S3.
        new_res["package_id"] = ds_dict["id"]
        # only admin users are allowed to set these values (extra security)
        for key in ["sha256", "etag"]:
            if key in new_res:
                if cur_res is None:
                    return {"success": False,
                            "msg": f"Regular users may not specify '{key}' "
                                   f"when creating a resource."}
                if cur_res.get(key) != new_res[key]:
                    return {"success": False,
                            "msg": f"Regular users may not edit '{key}'."}

        if cur_res is not None:
            # we are updating an existing resource
            aut = resource_update_check(context, new_res, ds_dict=ds_dict)
            if not aut["success"]:
                return aut
        else:
            # We are either creating a resource via an upload through
            # CKAN or we are creating a resource and have already uploaded
            # the file to S3 (we know `rid`). Both cases are covered in
            # this method:
            aut = resource_create_check(context, new_res, ds_dict=ds_dict)
            if not aut["success"]:
                return aut

    # do not allow changing things and uploading resources to non-drafts
    if ds_dict.get('state') != "draft":
        # these things are allowed to be in the data dictionary (see below)
        allowed_keys = [
            "license_id",  # see below, setting less restrictive license
            "private",  # see below, making dataset public
            "state",  # see below, not really important
        ]
        ignored_keys = [
            "pkg_name",  # this is sometimes present in the web interface
        ]
        ignored_empty_keys = [
            # keys that may be present if they are empty
            "tag_string",  # redundant with "tags"
        ]
        for key in data_dict:
            if key in ignored_keys:
                continue
            elif key in ignored_empty_keys and not data_dict[key]:
                # ignore some of the keys
                continue
            elif not data_dict[key] and not ds_dict.get(key):
                # ignore empty keys that are not in the original dict
                continue
            if data_dict[key] != ds_dict.get(key) and key not in allowed_keys:
                return {'success': False,
                        'msg': f"Changing '{key}' not allowed for non-draft "
                               + "datasets!"}

    # do not allow switching to a more restrictive license
    if "license_id" in data_dict:
        allowed = dcor_helpers.get_valid_licenses(ds_dict["license_id"])
        if data_dict["license_id"] not in allowed:
            return {'success': False,
                    'msg': 'Cannot switch to more-restrictive license'}

    # do not allow setting state from "active" to "draft"
    if ds_dict["state"] != "draft" and data_dict.get("state") == "draft":
        return {'success': False,
                'msg': 'Changing dataset state to draft not allowed'}

    # private dataset?
    must_be_private = not asbool(config.get(
        "ckanext.dcor_schemas.allow_public_datasets", "true"))
    private_default = must_be_private  # public if not has to be private
    is_private = asbool(data_dict.get('private', private_default))
    was_private = ds_dict["private"]
    assert isinstance(was_private, bool)
    if must_be_private:
        # has to be private
        if not is_private:
            # do not allow setting visibility from private to public if public
            # datasets are not allowed
            return {"success": False,
                    "msg": "Public datasets have been disabled via "
                           "the configuration option 'ckanext."
                           "dcor_schemas.allow_public_datasets = false'!"}
    else:
        # does not have to be private
        if not was_private and is_private:
            # do not allow setting the visibility from public to private
            return {'success': False,
                    'msg': 'Changing visibility to private not allowed'}

    # do not allow changing some of the keys (also for drafts)
    prohibited_keys = ["name"]
    invalid = {}
    for key in data_dict:
        if (key in ds_dict
            and key in prohibited_keys
                and data_dict[key] != ds_dict[key]):
            invalid[key] = data_dict[key]
    if invalid:
        return {'success': False,
                'msg': 'Editing not allowed: {}'.format(invalid)}

    return {'success': True}


def resource_create(context, data_dict=None):
    # original auth function
    aut = logic.auth.create.resource_create(context, data_dict)
    if not aut["success"]:
        return aut

    return resource_create_check(context, data_dict)


def resource_create_check(context, new_dict, ds_dict=None):
    aut = resource_auth_general(context, new_dict, ds_dict=ds_dict)
    if not aut["success"]:
        return aut

    if ds_dict is None:
        ds_dict = logic.get_action('package_show')(
            dict(context, return_type='dict'),
            {'id': new_dict["package_id"]})

    # resource id must not be set, unless the corresponding
    # S3 object exists
    rid = new_dict.get("id")
    if rid:
        # We want to ignore keys in the dictionary that did not change.
        unchanged_keys = []
        for res_dict_old in ds_dict["resources"]:
            if res_dict_old["id"] == rid:
                for key in new_dict:
                    if res_dict_old.get(key) == new_dict[key]:
                        unchanged_keys.append(key)
                break

        # Double-check that the resource does not already exist
        model = context['model']
        session = context['session']
        if session.query(model.Resource).get(rid):
            return {'success': False,
                    'msg': f'Resource {rid} already exists!'}
        bucket_name = get_ckan_config_option(
            "dcor_object_store.bucket_name").format(
            organization_id=ds_dict["organization"]["id"])
        object_name = f"resource/{rid[:3]}/{rid[3:6]}/{rid[6:]}"
        if not s3.object_exists(bucket_name=bucket_name,
                                object_name=object_name):
            return {'success': False,
                    'msg': f'Resource {rid} not available on S3!'}
        # Also make sure that the user did not specify more metadata
        # than allowed.
        allowed_keys = resource_editable_metadata().union(
            {"id", "name", "package_id", "s3_available"}).union(
                set(unchanged_keys))
        if not set(new_dict.keys()).issubset(allowed_keys):
            changed_keys = [k for k in new_dict if k not in allowed_keys]
            return {'success': False,
                    'msg': f'For resource uploads via S3, you may only '
                           f'change the metadata keys {sorted(allowed_keys)}. '
                           f'Got the following new or changed metadata keys: '
                           f'{sorted(changed_keys)}!'}
        if not new_dict.get("s3_available", True):
            return {'success': False,
                    'msg': '"s3_available" must be set to True'}
    else:
        # Legacy upload
        allowed_keys = resource_editable_metadata().union(
            # some of these are set by the uploader class
            {"name", "package_id", "upload", "url", "url_type",
             "last_modified", "mimetype", "size"})
        if not set(new_dict.keys()).issubset(allowed_keys):
            return {'success': False,
                    'msg': f'For legacy resource uploads, you may only '
                           f'specify the metadata {sorted(allowed_keys)}. "'
                           f'Got the following metadata keys: '
                           f' {sorted(new_dict.keys())}!'}

    return {'success': True}


def resource_editable_metadata():
    """Set of resource metadata keys that may be edited for draft datasets"""
    # "sp:*" keys and "description"
    return set(rss.get_composite_item_list() + ["description"])


def resource_auth_general(context, new_dict, ds_dict=None):
    """General checks for adding or changing resource data"""
    if "package_id" in new_dict:
        if ds_dict is None:
            ds_dict = logic.get_action('package_show')(
                dict(context, return_type='dict'),
                {'id': new_dict["package_id"]})

            # do not allow adding resources to non-draft datasets
            if ds_dict["state"] != "draft":
                return {'success': False,
                        'msg': 'Editing resources for non-draft datasets not '
                               'allowed!'}
    else:
        return {'success': False,
                'msg': 'No package_id specified!'}
    return {"success": True}


def resource_update(context, data_dict=None):
    # original auth function
    # (this also checks against package_update auth)
    aut = logic.auth.update.resource_update(context, data_dict)
    if not aut["success"]:
        return aut

    data_dict["package_id"] = get_package_id(context, data_dict)

    return resource_update_check(context, data_dict)


def resource_update_check(context, new_dict, ds_dict=None):
    """Check update of an *existing* resource

    Parameters
    ----------
    context:
        CKAN context
    new_dict:
        new resource dict
    ds_dict:
        current dataset dict containing the resource
    """
    rid = logic.get_or_bust(new_dict, "id")
    aut = resource_auth_general(context, new_dict, ds_dict=ds_dict)
    if not aut["success"]:
        return aut

    # get the current resource dict
    if ds_dict is None:
        old_dict = logic.get_action('resource_show')(
            context,
            {'id': rid})
    else:
        for res in ds_dict["resources"]:
            if res["id"] == rid:
                old_dict = res
                break
        else:
            return {'success': False,
                    'msg': f'Resource {rid} not in dataset!'}

    # only allow updating the description...
    allowed_keys = resource_editable_metadata()

    invalid = []
    for key in new_dict:
        if key in allowed_keys:
            continue
        elif key in old_dict and new_dict[key] == old_dict[key]:
            continue
        else:
            invalid.append(f"{key}={new_dict[key]}")
    if invalid:
        return {'success': False,
                'msg': f'Editing not allowed: {", ".join(invalid)}'}

    return {'success': True}


def resource_upload_s3_urls(context, data_dict):
    """Check whether the user is allowed to upload a resource to S3"""
    # TODO: Can these checks also be added to a validator method?
    if not data_dict or data_dict.get("organization_id") is None:
        return {'success': False,
                'msg': 'No `organization_id` provided'}
    if not data_dict or data_dict.get("file_size") is None:
        return {'success': False,
                'msg': 'No `file_size` provided'}
    org_id = data_dict["organization_id"]
    # Check whether the user can create a resource in the organization
    org_dicts = logic.get_action('organization_list_for_user')(
        context,
        {'id': authz.get_user_id_for_username(context["user"]),
         'permission': "create_dataset"})
    if org_id not in [od["id"] for od in org_dicts]:
        return {'success': False,
                'msg': f'User {context["user"]} not a member of '
                       f'the circle {org_id} or circle does not exist'}
    return {'success': True}


@logic.auth_allow_anonymous_access
def user_create(context, data_dict=None):
    """Measure against automated registration from gmail addresses

    This function is the first escalation of many more possible
    ways to restrict user registration via bots, e.g.

    - https://github.com/DCOR-dev/ckanext-dcor_schemas/issues/1
    - https://github.com/DCOR-dev/ckanext-dcor_schemas/issues/4
    - https://github.com/DCOR-dev/ckanext-dcor_schemas/issues/14

    Part of this (implementing as auth function) is actually
    security by obscurity. Anyone trying to register with a
    gmail address will just get a "403 Forbidden".

    Implementing this with IUserForm would be much better:
    https://github.com/ckan/ckan/issues/6070
    """
    # original auth function
    aut = logic.auth.create.user_create(context, data_dict)
    if not aut["success"]:
        return aut

    collected_data = {}
    spam_score = 0

    if data_dict is None:
        data_dict = {}

    for name_key in ["fullname", "name", "display_name", "email"]:
        name_val = data_dict.get(name_key, "").lower()
        collected_data[name_key] = name_val
        if name_val.count("xx"):
            # script kiddies
            spam_score += 1
        if name_val.count("/"):
            spam_score += 1
        if name_val.count("+"):
            spam_score += 1
        if len(name_val) > 30:
            spam_score += 1

    if "image_url" in data_dict:
        im_url = data_dict.get("image_url", "").lower()
        collected_data["image_url"] = im_url
        if im_url:
            if not re.search(r"\.(png|jpe?g)$", im_url):  # abuse!
                spam_score += 1
            if "abortion" in im_url:
                spam_score += 1

    if "email" in data_dict:
        # somebody is attempting to create a user
        email = data_dict.get("email", "").strip()
        collected_data["email"] = email
        if not email:
            return {'success': False,
                    'msg': 'No email address provided!'}
        else:
            email = parseaddr(email)[1]
            if (not email
                or "@" not in email
                    or "." not in email.split("@")[1]):
                # not a valid email address
                return {'success': False,
                        'msg': 'Invalid email address provided!'}
            domain = email.split("@")[1]
            # this might be a little harsh
            if domain in ["gmail.com", "mailto.plus"]:
                spam_score += 1

    if spam_score:
        return {'success': False,
                'msg': f'Spam bot{spam_score * "*"} {collected_data}'}

    return {'success': True}

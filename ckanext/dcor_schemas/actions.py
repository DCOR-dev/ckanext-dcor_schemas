import uuid

from ckan import model
from ckan.lib.dictization import model_dictize
import ckan.plugins.toolkit as toolkit

from dcor_shared import get_ckan_config_option, s3

from . import resource_schema_supplements as rss
from .validate import RESOURCE_EXTS


@toolkit.side_effect_free
def get_resource_upload_s3_urls(context, data_dict):
    """Return presigned URLs for uploading a resource to S3

    Parameters
    ----------
    context: dict
        CKAN context
    data_dict: dict
        Dictionary containing the key ID "organization_id", the
        organization ID containing the dataset to which the
        resource will belong.

    Once the file is uploaded, it is private by default. Setting the
    `public=true` tag to a resource will make it public. This is taken
    care of in CKAN's background jobs.
    """
    # The corresponding auth function already checks whether the user
    # is a member of the organization.
    org_id = data_dict["organization_id"]
    file_size = int(float(data_dict["file_size"]))
    bucket_name = get_ckan_config_option(
        "dcor_object_store.bucket_name").format(
        organization_id=org_id)
    # Create a random resource identifier and make sure it does not exist
    model = context['model']
    session = context['session']
    for ii in range(20):
        rid = str(uuid.uuid4())
        result = session.query(model.Resource).get(rid)
        if not result:
            break
    else:
        raise KeyError("Could not allocate a free UUID for a new resource")
    object_name = f"resource/{rid[:3]}/{rid[3:6]}/{rid[6:]}"
    upload_urls, complete_url = s3.create_presigned_upload_urls(
        bucket_name=bucket_name,
        object_name=object_name,
        file_size=file_size,
        # the default expiration time is 1 day
    )
    data = {
        "upload_urls": upload_urls,
        "complete_url": complete_url,
        "resource_id": rid,
    }
    return data


@toolkit.side_effect_free
def get_resource_schema_supplements(context, data_dict=None):
    """Dictionary of joined resource schema supplements"""
    schema = rss.load_schema_supplements()
    return schema


@toolkit.side_effect_free
def get_supported_resource_suffixes(context, data_dict=None):
    """List of supported resource suffixes"""
    return RESOURCE_EXTS


@toolkit.side_effect_free
def get_group_list_for_user(context, data_dict=None):
    """Return the collections (CKAN groups) a user is a member of

    In contrast to CKAN's `group_list_authz`, which only returns the
    collections a user may edit, this returns all collections in which
    the user has any capacity (member, editor, or admin). This is the
    collection-equivalent of `organization_list_for_user`.

    Parameters
    ----------
    context: dict
        CKAN context
    data_dict: dict
        May contain the key "id" with the name or ID of the user
        (defaults to the user making the request); only sysadmins
        may list the collections of other users.

    Returns
    -------
    collections: list of dict
        Collection dictionaries (as returned by `group_list` with
        `all_fields=True`), sorted by name
    """
    data_dict = data_dict or {}
    toolkit.check_access("dcor_group_list_for_user", context, data_dict)
    user_ref = data_dict.get("id") or context.get("user")
    user = model.User.get(user_ref) if user_ref else None
    if user is None:
        raise toolkit.ObjectNotFound("User not found")

    groups = (
        model.Session.query(model.Group)
        .join(model.Member, model.Member.group_id == model.Group.id)
        .filter(model.Member.table_name == "user")
        .filter(model.Member.table_id == user.id)
        .filter(model.Member.state == "active")
        .filter(model.Group.is_organization.is_(False))
        .filter(model.Group.state == "active")
        .distinct()
        .all()
    )
    return model_dictize.group_list_dictize(
        groups,
        context,
        sort_key=lambda x: x["name"],
        with_package_counts=False)

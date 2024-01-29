import uuid

import ckan.plugins.toolkit as toolkit

from dcor_shared import get_ckan_config_option, s3

from . import resource_schema_supplements as rss
from .validate import RESOURCE_EXTS


@toolkit.side_effect_free
def get_resource_upload_s3_url(context, data_dict):
    """Return a presigned URL for uploading a resource to S3

    Once the file is uploaded, it is private by default. Setting the
    `public=true` tag to a resource will make it public. This is taken
    care of in CKAN's background jobs.
    """
    # The corresponding auth function already checks whether the user
    # is a member of the organization.
    org_id = data_dict["organization_id"]
    bucket_name = get_ckan_config_option(
        "dcor_object_store.bucket_name").format(
        organization_id=org_id)
    # Create a random resource identifier
    rid = str(uuid.uuid4())
    object_name = f"resource/{rid[:3]}/{rid[3:6]}/{rid[6:]}"
    url, fields = s3.create_presigned_upload_url(
        bucket_name=bucket_name,
        object_name=object_name,
        # the default expiration time is 1 day
    )
    return {"url": url, "fields": fields}


@toolkit.side_effect_free
def get_resource_schema_supplements(context, data_dict=None):
    """Dictionary of joined resource schema supplements"""
    schema = rss.load_schema_supplements()
    return schema


@toolkit.side_effect_free
def get_supported_resource_suffixes(context, data_dict=None):
    """List of supported resource suffixes"""
    return RESOURCE_EXTS

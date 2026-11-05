import pathlib
import uuid

from dcor_shared import get_ckan_config_option, s3


def upload_resource_to_s3(path: str | pathlib.Path, ds_dict: dict) -> str:
    """Upload a file to S3 (without creating a CKAN resource)

    Returns the resource ID that must be used when creating the
    resource in CKAN.
    """
    rid = str(uuid.uuid4())
    bucket_name = get_ckan_config_option(
        "dcor_object_store.bucket_name").format(
        organization_id=ds_dict["owner_org"])
    s3.upload_file(bucket_name=bucket_name,
                   object_name=f"resource/{rid[:3]}/{rid[3:6]}/{rid[6:]}",
                   path=path,
                   private=ds_dict.get("private", False))
    return rid

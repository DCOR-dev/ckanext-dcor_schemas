from ckan import logic

import dclab
from dcor_shared import (
    DC_MIME_TYPES, get_resource_path, get_dc_instance, s3cc, sha256sum,
    wait_for_resource
)


def admin_context():
    return {'ignore_auth': True, 'user': 'default'}


def patch_resource_noauth(package_id, resource_id, data_dict):
    """Patch a resource using package_revise"""
    package_revise = logic.get_action("package_revise")
    revise_dict = {"match": {"id": package_id},
                   "update__resources__{}".format(resource_id): data_dict}
    package_revise(context=admin_context(), data_dict=revise_dict)


def set_dc_config_job(resource):
    """Store all DC config metadata"""
    if (resource.get('mimetype') in DC_MIME_TYPES
            and resource.get("dc:setup:channel width", None) is None):
        rid = resource["id"]
        wait_for_resource(rid)
        data_dict = {}
        with get_dc_instance(rid) as ds:
            for sec in dclab.dfn.CFG_METADATA:
                if sec in ds.config:
                    for key in dclab.dfn.config_keys[sec]:
                        if key in ds.config[sec]:
                            dckey = 'dc:{}:{}'.format(sec, key)
                            value = ds.config[sec][key]
                            data_dict[dckey] = value
        patch_resource_noauth(
            package_id=resource["package_id"],
            resource_id=rid,
            data_dict=data_dict)
        return True
    return False


def set_format_job(resource):
    """Writes the correct format to the resource metadata"""
    mimetype = resource.get("mimetype")
    rformat = resource.get("format")
    if mimetype in DC_MIME_TYPES and rformat in [mimetype, None]:
        rid = resource["id"]
        # (if format is already something like RT-FDC then we don't do this)
        wait_for_resource(rid)
        ds = get_dc_instance(rid)
        with ds, dclab.IntegrityChecker(ds) as ic:
            if ic.has_fluorescence:
                fmt = "RT-FDC"
            else:
                fmt = "RT-DC"
        if rformat != fmt:  # only update if necessary
            patch_resource_noauth(
                package_id=resource["package_id"],
                resource_id=rid,
                data_dict={"format": fmt})
            return True
    return False


def set_s3_resource_metadata(resource):
    """Set the s3_url and s3_available metadata for the resource"""
    rid = resource["id"]
    if s3cc.artifact_exists(resource_id=rid, artifact="resource"):
        s3_url = s3cc.get_s3_url_for_artifact(resource_id=rid)
        patch_resource_noauth(
            package_id=resource["package_id"],
            resource_id=resource["id"],
            data_dict={"s3_available": True,
                       "s3_url": s3_url})


def set_s3_resource_public_tag(resource):
    """Set the public=True tag to an S3 object if the dataset is public"""
    # Determine whether the resource is public
    ds_dict = logic.get_action('package_show')(
        admin_context(),
        {'id': resource["package_id"]})
    private = ds_dict.get("private")
    if private is not None and not private:
        s3cc.make_resource_public(
            resource_id=resource["id"],
            # The resource might not be there, because it was uploaded
            # using the API and not to S3.
            missing_ok=True,
        )


def set_sha256_job(resource):
    """Computes the sha256 hash and writes it to the resource metadata"""
    sha = str(resource.get("sha256", ""))  # can be bool sometimes
    rid = resource["id"]
    if len(sha) != 64:  # only compute if necessary
        wait_for_resource(rid)
        path = get_resource_path(rid)
        if path.exists():
            # The file exists locally on block storage
            rhash = sha256sum(path)
        else:
            # The file exists on S3 object storage
            rhash = s3cc.compute_checksum(rid)
        patch_resource_noauth(
            package_id=resource["package_id"],
            resource_id=resource["id"],
            data_dict={"sha256": rhash})
        return True
    return False

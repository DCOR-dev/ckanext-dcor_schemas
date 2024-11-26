from ckan import logic

import dclab
from dcor_shared import (
    DC_MIME_TYPES, get_ckan_config_option, get_dc_instance, get_resource_path,
    rqjob_register, s3, s3cc, sha256sum, wait_for_resource,
)
from dcor_shared import RQJob  # noqa: F401


def admin_background_context():
    return {'ignore_auth': True,
            'user': 'default',
            'is_background_job': True,
            }


def get_base_metadata(resource):
    res_dict_base = {}
    suffix = "." + resource["name"].rsplit(".", 1)[-1]
    for mt in DC_MIME_TYPES:
        if suffix in DC_MIME_TYPES[mt]:
            res_dict_base["mimetype"] = mt
            break

    # Also make sure the resource has "url" defined.
    site_url = get_ckan_config_option("ckan.site_url")
    meta_url = (f"{site_url}"
                f"/dataset/{resource['package_id']}"
                f"/resource/{resource['id']}"
                f"/download/{resource['name'].lower()}")
    res_dict_base["url"] = meta_url
    return res_dict_base


def patch_resource_noauth(package_id, resource_id, data_dict):
    """Patch a resource using package_revise"""
    package_revise = logic.get_action("package_revise")
    revise_dict = {"match": {"id": package_id},
                   "update__resources__{}".format(resource_id): data_dict}
    package_revise(context=admin_background_context(), data_dict=revise_dict)


@rqjob_register(ckanext="dcor_schemas",
                queue="dcor-short")
def job_set_resource_metadata_base(resource):
    """Set basic resource metadata

    `package_revise` calls `after_dataset_update` which calls
    `after_resource_create` in the dcor_schemas plugin. But in
    `after_resource_create`, we only run jobs that have not been
    run before. So it makes sense to perform any additional calls
    to `package_revise` in those background jobs.

    Notes
    -----
    This method exists as a workaround to avoid circular code. When this
    method calls `patch_resource_noauth`, it does so with the
    `admin_background_context`, preventing any other background jobs from
    being triggered.
    """
    res_dict_base = get_base_metadata(resource)
    patch_resource_noauth(
        package_id=resource["package_id"],
        resource_id=resource["id"],
        data_dict=res_dict_base)
    return True


@rqjob_register(ckanext="dcor_schemas",
                queue="dcor-normal",
                timeout=500,
                depends_on=["job_set_resource_metadata_base",
                            "job_set_dc_format",
                            ])
def job_set_dc_config(resource):
    """Store all DC config metadata"""
    resource.update(get_base_metadata(resource))
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


@rqjob_register(ckanext="dcor_schemas",
                queue="dcor-short",
                timeout=300,
                at_front=True)
def job_set_etag(resource):
    """Set the resource ETag extracted from S3"""
    etag = str(resource.get("etag", ""))
    rid = resource["id"]
    # Example ETags:
    # - "69725a2f8ea27a47401960990377188b": MD5 sum of a file
    # - "81a89c74b50282fc02e4faa7b654a05a-4": multipart upload
    if len(etag.split("-")[0]) != 32:  # only compute if necessary
        wait_for_resource(rid)
        path = get_resource_path(rid)
        if path.exists():
            # We just don't do it. ETags are only for datasets that
            # were uploaded to S3.
            pass
        else:
            # The file exists on S3 object storage
            bucket_name, object_name = s3cc.get_s3_bucket_object_for_artifact(
                resource_id=rid, artifact="resource")
            s3_client, _, _ = s3.get_s3()
            meta = s3_client.head_object(Bucket=bucket_name, Key=object_name)
            if "ETag" in meta:
                etag = meta["ETag"].strip("'").strip('"')
                patch_resource_noauth(
                    package_id=resource["package_id"],
                    resource_id=resource["id"],
                    data_dict={"etag": etag})
            return True
    return False


@rqjob_register(ckanext="dcor_schemas",
                queue="dcor-short",
                timeout=500,
                depends_on=["job_set_resource_metadata_base",
                            "job_set_etag",
                            ])
def job_set_dc_format(resource):
    """Writes the correct format to the resource metadata"""
    mimetype = resource.get("mimetype")
    rformat = resource.get("format")
    if mimetype in DC_MIME_TYPES and rformat in [mimetype, None, ""]:
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


@rqjob_register(ckanext="dcor_schemas",
                queue="dcor-short",
                timeout=500,
                )
def job_set_s3_resource_metadata(resource):
    """Set S3-related resource metadata"""
    rid = resource["id"]
    if (("s3_available" not in resource or "s3_url" not in resource)
            and s3cc.artifact_exists(resource_id=rid, artifact="resource")):
        s3_url = s3cc.get_s3_url_for_artifact(resource_id=rid)
        res_new_dict = {"s3_available": True,
                        "s3_url": s3_url,
                        }
        if not resource.get("size"):
            # Resource has been uploaded via S3 and CKAN did not pick up
            # the size.
            meta = s3cc.get_s3_attributes_for_artifact(rid)
            res_new_dict["size"] = meta["size"]
        if not resource.get("url_type"):
            # Resource has been uploaded via S3 and CKAN did not set the
            # url_type to "upload". Here we set it to "s3_upload" to
            # clarify this.
            res_new_dict["url_type"] = "s3_upload"
        patch_resource_noauth(
            package_id=resource["package_id"],
            resource_id=resource["id"],
            data_dict=res_new_dict)


@rqjob_register(ckanext="dcor_schemas",
                queue="dcor-short",
                timeout=300,
                )
def job_set_s3_resource_public_tag(resource):
    """Set the public=True tag to an S3 object if the dataset is public"""
    # Determine whether the resource is public
    ds_dict = logic.get_action('package_show')(
        admin_background_context(),
        {'id': resource["package_id"]})
    private = ds_dict.get("private")
    if private is not None and not private:
        s3cc.make_resource_public(
            resource_id=resource["id"],
            # The resource might not be there, because it was uploaded
            # using the API and not to S3.
            missing_ok=True,
        )


@rqjob_register(ckanext="dcor_schemas",
                queue="dcor-long",
                timeout=3600,
                )
def job_set_sha256(resource):
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

import hashlib

from ckan import logic

import dclab
from dcor_shared import DC_MIME_TYPES, get_resource_path, wait_for_resource


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
        path = get_resource_path(resource["id"])
        wait_for_resource(path)
        data_dict = {}
        with dclab.new_dataset(path) as ds:
            for sec in dclab.dfn.CFG_METADATA:
                if sec in ds.config:
                    for key in dclab.dfn.config_keys[sec]:
                        if key in ds.config[sec]:
                            dckey = 'dc:{}:{}'.format(sec, key)
                            value = ds.config[sec][key]
                            data_dict[dckey] = value
        patch_resource_noauth(
            package_id=resource["package_id"],
            resource_id=resource["id"],
            data_dict=data_dict)
        return True
    return False


def set_format_job(resource):
    """Writes the correct format to the resource metadata"""
    mimetype = resource.get("mimetype")
    rformat = resource.get("format")
    if mimetype in DC_MIME_TYPES and rformat in [mimetype, None]:
        # (if format is already something like RT-FDC then we don't do this)
        path = get_resource_path(resource["id"])
        wait_for_resource(path)
        with dclab.rtdc_dataset.check.IntegrityChecker(path) as ic:
            if ic.has_fluorescence:
                fmt = "RT-FDC"
            else:
                fmt = "RT-DC"
        if rformat != fmt:  # only update if necessary
            patch_resource_noauth(
                package_id=resource["package_id"],
                resource_id=resource["id"],
                data_dict={"format": fmt})
            return True
    return False


def set_sha256_job(resource):
    """Computes the sha256 hash and writes it to the resource metadata"""
    sha = str(resource.get("sha256", ""))  # can be bool sometimes
    if len(sha) != 64:  # only compute if necessary
        path = get_resource_path(resource["id"])
        wait_for_resource(path)
        file_hash = hashlib.sha256()
        with open(path, "rb") as fd:
            while True:
                data = fd.read(2**20)
                if not data:
                    break
                file_hash.update(data)
        sha256sum = file_hash.hexdigest()
        patch_resource_noauth(
            package_id=resource["package_id"],
            resource_id=resource["id"],
            data_dict={"sha256": sha256sum})
        return True
    return False

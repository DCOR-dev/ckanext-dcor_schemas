import hashlib
import time

from ckan import logic

import dclab
from dcor_shared import DC_MIME_TYPES, get_resource_path, wait_for_resource


def admin_context():
    return {'ignore_auth': True, 'user': 'default'}


def patch_resource_noauth(data_dict):
    """Patch a resource and make sure that the patch was applied"""
    resource_patch = logic.get_action("resource_patch")
    resource_show = logic.get_action("resource_show")

    # https://github.com/ckan/ckan/issues/2017
    while True:
        resource_patch(context=admin_context(),
                       data_dict=data_dict)
        rs = resource_show(context=admin_context(),
                           data_dict={"id": data_dict["id"]})
        for key in data_dict:
            # do it again
            if data_dict[key] != rs[key]:
                time.sleep(0.01)
                break
        else:
            # everything matches up
            break


def set_dc_config_job(resource):
    """Store all DC config metadata"""
    if resource.get('mimetype') in DC_MIME_TYPES:
        path = get_resource_path(resource["id"])
        wait_for_resource(path)
        data_dict = {"id": resource["id"]}
        with dclab.new_dataset(path) as ds:
            for sec in dclab.dfn.CFG_METADATA:
                if sec in ds.config:
                    for key in dclab.dfn.config_keys[sec]:
                        if key in ds.config[sec]:
                            dckey = 'dc:{}:{}'.format(sec, key)
                            value = ds.config[sec][key]
                            data_dict[dckey] = value
        patch_resource_noauth(data_dict=data_dict)


def set_format_job(resource):
    """Writes the correct format to the resource metadata"""
    if resource.get('mimetype') in DC_MIME_TYPES:
        path = get_resource_path(resource["id"])
        wait_for_resource(path)
        with dclab.rtdc_dataset.check.IntegrityChecker(path) as ic:
            if ic.has_fluorescence:
                fmt = "RT-FDC"
            else:
                fmt = "RT-DC"
        patch_resource_noauth(data_dict={"id": resource["id"],
                                         "format": fmt})


def set_sha256_job(resource):
    """Computes the sha256 hash and writes it to the resource metadata"""
    if not resource.get("sha256", "").strip():  # only compute if necessary
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
        patch_resource_noauth(data_dict={"id": resource["id"],
                                         "sha256": sha256sum})

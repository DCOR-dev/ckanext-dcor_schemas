import hashlib
import pathlib
import time

import ckan.lib.uploader as uploader
from ckan import logic
import ckan.plugins.toolkit as toolkit

import dclab
from dcor_shared import DC_MIME_TYPES, wait_for_resource


def get_dataset_path(context, resource):
    resource_id = resource["id"]
    rsc = toolkit.get_action('resource_show')(context, {'id': resource_id})
    upload = uploader.ResourceUpload(rsc)
    filepath = upload.get_path(rsc['id'])
    return filepath


def patch_resource_noauth(data_dict):
    """Patch a resource and make sure that the patch was applied"""
    resource_patch = logic.get_action("resource_patch")
    resource_show = logic.get_action("resource_show")

    # https://github.com/ckan/ckan/issues/2017
    while True:
        resource_patch(context={'ignore_auth': True,
                                'user': None},
                       data_dict=data_dict)
        rs = resource_show(context={'ignore_auth': True},
                           data_dict={"id": data_dict["id"]})
        for key in data_dict:
            # do it again
            if data_dict[key] != rs[key]:
                time.sleep(0.01)
                break
        else:
            # everything matches up
            break


def set_dc_config_job(path, resource):
    """Store all DC config metadata"""
    path = pathlib.Path(path)
    wait_for_resource(path)
    mtype = resource.get('mimetype')
    if mtype in DC_MIME_TYPES:
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


def set_format_job(path, resource):
    """Writes the correct format to the resource metadata"""
    if resource.get('mimetype') in DC_MIME_TYPES:
        wait_for_resource(path)
        with dclab.rtdc_dataset.check.IntegrityChecker(path) as ic:
            if ic.has_fluorescence:
                fmt = "RT-FDC"
            else:
                fmt = "RT-DC"
        patch_resource_noauth(data_dict={"id": resource["id"],
                                         "format": fmt})


def set_sha256_job(path, resource):
    """Computes the sha256 hash and writes it to the resource metadata"""
    if not resource.get("sha256", "").strip():  # only compute if necessary
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

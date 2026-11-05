import cgi
import pathlib
import shutil
import tempfile
from unittest import mock

import pytest

import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers

from dcor_shared.testing import make_dataset_via_s3, synchronous_enqueue_job

import h5py
import numpy as np

from .helper_methods import upload_resource_to_s3

data_path = pathlib.Path(__file__).parent / "data"


def create_resource_via_s3(context, ds_dict, path, name, **kwargs):
    """Upload a file to S3 and add it to a dataset like DCOR-Aid does"""
    rid = upload_resource_to_s3(path, ds_dict)
    res_dict = {"id": rid, "name": name, "s3_available": True}
    res_dict.update(kwargs)
    ds_dict = helpers.call_action(
        "package_revise", context,
        match={"id": ds_dict["id"]},
        update__resources__extend=[res_dict])["package"]
    return ds_dict["resources"][-1]


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_configuration_metadata():
    """configuration metadata (using `dclab.dfn.config_funcs`)"""
    create_context = {'ignore_auth': True,
                      'user': "default",
                      'api_version': 3}
    ds_dict = make_dataset_via_s3(activate=False)
    path = data_path / "calibration_beads_47.rtdc"
    with path.open('rb') as fd:
        upload = cgi.FieldStorage()
        upload.filename = path.name
        upload.file = fd
        res = helpers.call_action("resource_create", create_context,
                                  package_id=ds_dict["id"],
                                  upload=upload,
                                  url="upload",
                                  name=path.name,
                                  # We have to add them as kwargs dict
                                  **{"dc:experiment:event count": "47",
                                     "dc:experiment:time": "10:04:03"}
                                  )

    assert res["dc:experiment:event count"] == 47
    assert res["dc:experiment:time"] == "10:04:03"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_configuration_metadata_invalid():
    """test for invalid metadata"""
    create_context = {'ignore_auth': True,
                      'user': "default",
                      'api_version': 3}

    ds_dict = make_dataset_via_s3(activate=False)
    path = data_path / "calibration_beads_47.rtdc"
    with path.open('rb') as fd:
        upload = cgi.FieldStorage()
        upload.filename = path.name
        upload.file = fd
        with pytest.raises(logic.ValidationError):
            helpers.call_action("resource_create", create_context,
                                package_id=ds_dict["id"],
                                upload=upload,
                                url="upload",
                                name=path.name,
                                # We have to add them as kwargs dict
                                **{"dc:experiment:event count": "peter"}
                                )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_configuration_supplement():
    """supplementary resource parameters"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'],
                       'api_version': 3}
    ds_dict = make_dataset_via_s3(
        create_context=create_context1,
        owner_org=owner_org,
        activate=False)
    path = data_path / "calibration_beads_47.rtdc"
    res = create_resource_via_s3(
        create_context1, ds_dict, path, path.name,
        **{"sp:general:sample type": "artificial",
           "sp:experiment:average brightness": 2.1})
    assert res["sp:general:sample type"] == "artificial"
    assert res["sp:experiment:average brightness"] == 2.1


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_configuration_supplement_invalid_value():
    """test whether "sp:cells:passage number": "peter" is an invalid value"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'],
                       'api_version': 3}
    ds_dict = make_dataset_via_s3(
        create_context=create_context1,
        owner_org=owner_org,
        activate=False)
    path = data_path / "calibration_beads_47.rtdc"
    with pytest.raises(logic.ValidationError):
        create_resource_via_s3(
            create_context1, ds_dict, path, path.name,
            **{"sp:general:sample type": "primary cells",
               "sp:cells:passage number": "peter"})


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_package_id_missing():
    """resource cannot be created without package"""
    user = factories.User()
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}

    path = data_path / "calibration_beads_47.rtdc"
    with path.open('rb') as fd:
        upload = cgi.FieldStorage()
        upload.filename = path.name
        upload.file = fd
        with pytest.raises(logic.ValidationError):
            helpers.call_action("resource_create", create_context,
                                upload=upload,
                                url="upload",
                                name=path.name,
                                )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_restrict_extensions():
    """restrict upload data extensions"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'],
                       'api_version': 3}
    ds_dict = make_dataset_via_s3(
        create_context=create_context1,
        owner_org=owner_org,
        activate=False)
    tdir = tempfile.mkdtemp(prefix="test_dcor_schemas_")
    path = pathlib.Path(tdir) / "bad_extension.docx"
    path.write_text("lorem ipsum doesn't want Word in data repositories")
    # create the first resource
    with pytest.raises(logic.ValidationError):
        create_resource_via_s3(
            create_context1, ds_dict, path, path.name)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_same_name_forbidden():
    """do not allow uploading resources with the same name"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'],
                       'api_version': 3}
    ds_dict = make_dataset_via_s3(
        create_context=create_context1,
        owner_org=owner_org,
        activate=False)
    path = data_path / "calibration_beads_47.rtdc"
    # create the first resource
    create_resource_via_s3(
        create_context1, ds_dict, path, path.name)
    # attempt creation of second resource with same name
    create_context2 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}
    with pytest.raises(logic.ValidationError):
        create_resource_via_s3(
            create_context2, ds_dict, path, path.name)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_same_name_as_second_resource_forbidden():
    """do not allow a new resource with the name of a later resource"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    create_context = {'ignore_auth': False,
                      'user': user['name'],
                      'api_version': 3}
    ds_dict = make_dataset_via_s3(
        create_context=create_context,
        owner_org=owner_org,
        activate=False)
    path = data_path / "calibration_beads_47.rtdc"
    create_resource_via_s3(create_context, ds_dict, path, "a.rtdc")
    create_resource_via_s3(create_context, ds_dict, path, "b.rtdc")
    with pytest.raises(logic.ValidationError):
        create_resource_via_s3(create_context, ds_dict, path, "b.rtdc")


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_update_supplement_of_second_resource():
    """updating a resource must not conflict with its own name

    DCOR-Aid sets the supplementary resource metadata after the upload
    with `package_revise`.
    """
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    create_context = {'ignore_auth': False,
                      'user': user['name'],
                      'api_version': 3}
    ds_dict = make_dataset_via_s3(
        create_context=create_context,
        owner_org=owner_org,
        activate=False)
    path = data_path / "calibration_beads_47.rtdc"
    create_resource_via_s3(create_context, ds_dict, path, "a.rtdc")
    res2 = create_resource_via_s3(create_context, ds_dict, path, "b.rtdc")
    ds_dict = helpers.call_action(
        "package_revise", create_context,
        match={"id": ds_dict["id"]},
        **{f"update__resources__{res2['id']}": {
            "sp:general:sample type": "artificial"}})["package"]
    assert ds_dict["resources"][1]["name"] == "b.rtdc"
    assert ds_dict["resources"][1]["sp:general:sample type"] == "artificial"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_weird_characters():
    """do not allow weird characters in resource names"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}
    ds_dict = make_dataset_via_s3(
        create_context=create_context1,
        owner_org=owner_org,
        activate=False)
    path = data_path / "calibration_beads_47.rtdc"
    tdir = tempfile.mkdtemp(prefix="test_dcor_schemas_")
    path2 = pathlib.Path(tdir) / "µæsdqow.rtdc"
    shutil.copy2(path, path2)
    # create the first resource
    with pytest.raises(logic.ValidationError):
        create_resource_via_s3(
            create_context1, ds_dict, path2, path2.name)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dc_serve dc_view')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@mock.patch('ckan.plugins.toolkit.enqueue_job',
            side_effect=synchronous_enqueue_job)
def test_resource_metadata_has_nan_value_ignored(enqueue_job_mock, tmp_path):
    """author list "authors" is CSV"""
    res_path = tmp_path / "custom_data.rtdc"
    shutil.copy2(data_path / "calibration_beads_47.rtdc", res_path)

    # Put NaN in the metadata
    with h5py.File(res_path, "a") as h5:
        h5.attrs["setup:flow rate"] = np.nan

    _, res_dict = make_dataset_via_s3(
        resource_path=res_path,
        activate=True,
        private=False,
        )

    # Fetch the metadata.
    res_dict = helpers.call_action("resource_show",
                                   id=res_dict["id"],
                                   )
    assert res_dict["dc:setup:channel width"] == 20
    assert "dc:setup:flow rate" not in res_dict

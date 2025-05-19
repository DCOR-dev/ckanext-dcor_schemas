import cgi
import pathlib
import uuid

import pytest

import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
from ckan import model

from dcor_shared.testing import make_dataset_via_s3, make_resource_via_s3


data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_id_forbidden():
    """do not allow setting a resource id when uploading"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    test_context = {'ignore_auth': False,
                    'user': user['name'], 'model': model, 'api_version': 3}
    # create a dataset
    ds_dict = make_dataset_via_s3(
        create_context=create_context,
        owner_org=owner_org,
        activate=False)
    path = data_path / "calibration_beads_47.rtdc"
    with path.open('rb') as fd:
        upload = cgi.FieldStorage()
        upload.filename = path.name
        upload.file = fd
        with pytest.raises(logic.NotAuthorized):
            helpers.call_auth("resource_create", test_context,
                              package_id=ds_dict["id"],
                              upload=upload,
                              url="upload",
                              name=path.name,
                              id=str(uuid.uuid4()),
                              )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_create_in_other_users_dataset():
    """User is not allowed to create a resource in another user's dataset"""
    user_a = factories.User()
    user_b = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user_a['id'],
        'capacity': 'admin'
    }])
    factories.Group(users=[
        {'name': user_a['id'], 'capacity': 'admin'},
    ])
    context_a = {'ignore_auth': False,
                 'user': user_a['name'], 'model': model, 'api_version': 3}
    context_b = {'ignore_auth': False,
                 'user': user_b['name'], 'model': model, 'api_version': 3}

    ds_dict, _ = make_dataset_via_s3(
        create_context=context_a,
        owner_org=owner_org,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=False)

    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("resource_create", context_b,
                          package_id=ds_dict["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_delete_only_drafts():
    """do not allow deleting resources unless they are drafts"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    test_context = {'ignore_auth': False,
                    'user': user['name'], 'model': model, 'api_version': 3}
    # create a dataset
    ds_dict = make_dataset_via_s3(
        create_context=create_context,
        owner_org=owner_org)
    assert ds_dict["state"] == "draft", "dataset without res must be draft"
    # assert: draft datasets may be deleted
    assert helpers.call_auth("package_delete", test_context,
                             id=ds_dict["id"])
    # upload resource
    rid = make_resource_via_s3(
        resource_path=data_path / "calibration_beads_47.rtdc",
        organization_id=owner_org['id'],
        dataset_id=ds_dict["id"],
        )
    # set dataset state to active
    helpers.call_action("package_patch", create_context,
                        id=ds_dict["id"],
                        state="active")
    # check dataset state
    dataset2 = helpers.call_action("package_show", create_context,
                                   id=ds_dict["id"])
    assert dataset2["state"] == "active"
    # check resource state
    res2 = helpers.call_action("resource_show", create_context,
                               id=rid)
    assert res2["state"] == "active"
    # assert: active resources may not be deleted
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("resource_delete", test_context,
                          id=rid)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
def test_resource_patch_only_description():
    """only allow changing the description"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'],
                      'api_version': 3}

    # create a dataset
    ds_dict, res_dict = make_dataset_via_s3(
        create_context=create_context,
        owner_org=owner_org,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=False)
    # assert: allow updating the description
    assert helpers.call_auth("resource_patch", create_context,
                             id=res_dict["id"],
                             package_id=ds_dict["id"],
                             description="my nice text")
    # assert: do not allow updating other things
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("resource_patch", create_context,
                          id=res_dict["id"],
                          package_id=ds_dict["id"],
                          name="hans.rtdc")
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("resource_patch", create_context,
                          id=res_dict["id"],
                          package_id=ds_dict["id"],
                          format="UnknownDC")
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("resource_patch", create_context,
                          id=res_dict["id"],
                          package_id=ds_dict["id"],
                          hash="doesntmakesense")
    sha = "490efdf5d9bb4cd4b2a6bcf2fe54d4dc201c38530140bcb168980bf8bf846c72"
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("resource_patch", create_context,
                          id=res_dict["id"],
                          package_id=ds_dict["id"],
                          sha256=sha)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_resource_patch_other_users_dataset():
    """User is not allowed to patch other user's datasets"""
    user_a = factories.User()
    user_b = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user_a['id'],
        'capacity': 'admin'
    }])
    factories.Group(users=[
        {'name': user_a['id'], 'capacity': 'admin'},
    ])
    context_a = {'ignore_auth': False,
                 'user': user_a['name'], 'model': model, 'api_version': 3}
    context_b = {'ignore_auth': False,
                 'user': user_b['name'], 'model': model, 'api_version': 3}

    # create a dataset
    ds_dict, res_dict = make_dataset_via_s3(
        create_context=context_a,
        owner_org=owner_org,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True)

    with pytest.raises(logic.NotAuthorized):
        assert helpers.call_auth("resource_patch", context_b,
                                 id=res_dict["id"],
                                 package_id=ds_dict["id"],
                                 description="my nice text")

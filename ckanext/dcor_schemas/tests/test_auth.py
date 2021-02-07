import cgi
import pathlib

import pytest

import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
from ckan import model


data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_delete_only_drafts():
    """do not allow deleting datasets or resources unless they are drafts"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # create dataset (`call_action` bypasses authorization!)
    create_context = {'ignore_auth': False, 'user': user['name']}
    dataset = helpers.call_action("package_create", create_context,
                                  title="test-dataset",
                                  authors="Peter Pan",
                                  license_id="CC-BY-4.0",
                                  owner_org=owner_org["name"],
                                  state="active",
                                  )
    assert dataset["state"] == "draft", "dataset without res must be draft"
    # upload resource
    path = data_path / "calibration_beads_47.rtdc"
    with path.open('rb') as fd:
        upload = cgi.FieldStorage()
        upload.filename = path.name
        upload.file = fd
        helpers.call_action("resource_create", create_context,
                            package_id=dataset["id"],
                            upload=upload,
                            url="upload",
                            name=path.name,
                            )
    # check dataset state
    dataset2 = helpers.call_action("package_show", create_context,
                                   id=dataset["id"])
    assert dataset2["state"] == "active", "dataset with a res must be active"
    # try to delete it
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_delete", test_context,
                          id=dataset["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_user_create_datasets():
    """allow all logged-in users to create datasets"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    context = {'ignore_auth': False, 'user': user['name'], "model": model}
    success = helpers.call_auth("package_create", context,
                                title="test-group",
                                authors="Peter Pan",
                                license_id="CC-BY-4.0",
                                owner_org=owner_org["id"],
                                )
    assert success


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_user_create_circles():
    """allow all logged-in users to create circles"""
    user = factories.User()
    context = {'ignore_auth': False, 'user': user['name'], "model": model}
    success = helpers.call_auth("organization_create", context,
                                name="test-org")
    assert success


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_user_create_collections():
    """allow all logged-in users to create collections"""
    user = factories.User()
    context = {'ignore_auth': False, 'user': user['name'], "model": model}
    success = helpers.call_auth("group_create", context, name="test-group")
    assert success

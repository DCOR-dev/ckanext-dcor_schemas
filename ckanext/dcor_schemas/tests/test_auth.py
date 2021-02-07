import cgi
import pathlib

import pytest

import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
from ckan import model


data_path = pathlib.Path(__file__).parent / "data"


def make_dataset(create_context, owner_org, with_resource=False,
                 activate=False):
    # create a dataset
    ds = helpers.call_action("package_create", create_context,
                             title="test-dataset",
                             authors="Peter Pan",
                             license_id="CC-BY-4.0",
                             owner_org=owner_org["name"],
                             state="draft",
                             )
    if with_resource:
        rs = make_resource(create_context, dataset_id=ds["id"])

    if activate:
        helpers.call_action("package_patch", create_context,
                            id=ds["id"],
                            state="active")

    dataset = helpers.call_action("package_show", id=ds["id"])

    if with_resource:
        resource = helpers.call_action("resource_show", id=rs["id"])
        return dataset, resource
    else:
        return dataset


def make_resource(create_context, dataset_id):
    path = data_path / "calibration_beads_47.rtdc"
    with path.open('rb') as fd:
        upload = cgi.FieldStorage()
        upload.filename = path.name
        upload.file = fd
        res = helpers.call_action("resource_create", create_context,
                                  package_id=dataset_id,
                                  upload=upload,
                                  url="upload",
                                  name=path.name,
                                  )
    return res


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_delete_only_drafts():
    """do not allow deleting datasets or resources unless they are drafts"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    dataset = make_dataset(create_context, owner_org, with_resource=False)
    assert dataset["state"] == "draft", "dataset without res must be draft"
    # assert: draft datasets may be deleted
    assert helpers.call_auth("package_delete", test_context,
                             id=dataset["id"])
    # upload resource
    res = make_resource(create_context, dataset_id=dataset["id"])
    # set dataset state to active
    helpers.call_action("package_patch", create_context,
                        id=dataset["id"],
                        state="active")
    # check dataset state
    dataset2 = helpers.call_action("package_show", create_context,
                                   id=dataset["id"])
    assert dataset2["state"] == "active"
    # assert: active datasets may not be deleted
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_delete", test_context,
                          id=dataset["id"])
    # check resource state
    res2 = helpers.call_action("resource_show", create_context,
                               id=res["id"])
    assert res2["state"] == "active"
    # assert: active resources may not be deleted
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("resource_delete", test_context,
                          id=res["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_purge_deleted():
    """do not allow deleting datasets or resources unless they are drafts"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    dataset = make_dataset(create_context, owner_org, with_resource=False)
    # delete a dataset
    helpers.call_action("package_delete", create_context,
                        id=dataset["id"]
                        )
    # assert: check that we can purge it
    assert helpers.call_auth("dataset_purge", test_context,
                             id=dataset["id"])


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_state_from_active_to_draft_forbidden():
    """do not allow setting the dataset state from active to draft"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    dataset, res = make_dataset(create_context, owner_org, with_resource=True,
                                activate=True)
    assert dataset["state"] == "active"
    # assert: cannot set state back to draft
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_patch", test_context,
                          id=dataset["id"],
                          state="draft")


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

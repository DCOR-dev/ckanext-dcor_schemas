import pytest

import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
from ckan import model

from .helper_methods import make_dataset, make_resource


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_delete_only_drafts():
    """do not allow deleting datasets unless they are drafts"""
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
    make_resource(create_context, dataset_id=dataset["id"])
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
def test_dataset_license_less_restrictive_forbidden():
    """dataset: do not allow switching to a more restrictive license"""
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
                                activate=True, license_id="CC0-1.0")
    # assert: cannot set license id to something less restrictive
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("package_patch", test_context,
                          id=dataset["id"],
                          license_id="CC-BY-4.0")


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

import pytest

import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
from ckan import model

from .helper_methods import make_dataset, make_resource


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
def test_resource_patch_only_description():
    """do not allow deleting resources unless they are drafts"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}
    test_context = {'ignore_auth': False, 'user': user['name'], "model": model}
    # create a dataset
    ds, res = make_dataset(create_context, owner_org, with_resource=True,
                           activate=True)
    # assert: allow updating the description
    assert helpers.call_auth("resource_patch", test_context,
                             id=res["id"],
                             package_id=ds["id"],
                             description="my nice text")
    # assert: do not allow updating other things
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("resource_patch", test_context,
                          id=res["id"],
                          package_id=ds["id"],
                          name="hans.rtdc")
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("resource_patch", test_context,
                          id=res["id"],
                          package_id=ds["id"],
                          format="UnknownDC")
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("resource_patch", test_context,
                          id=res["id"],
                          package_id=ds["id"],
                          hash="doesntmakesense")

import pytest

import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers
from ckan import model

from dcor_shared.testing import make_dataset


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_org_admin_bulk_update_delete_forbidden(create_with_upload):
    """do not allow bulk_update_delete"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # create a datasets
    create_context1 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}
    ds1, _ = make_dataset(create_context1, owner_org,
                          create_with_upload=create_with_upload,
                          activate=True)
    create_context2 = {'ignore_auth': False,
                       'user': user['name'], 'api_version': 3}
    ds2, _ = make_dataset(create_context2, owner_org,
                          create_with_upload=create_with_upload,
                          activate=True)
    # assert: bulk_update_delete is should be forbidden
    test_context = {'ignore_auth': False,
                    'user': user['name'], 'model': model, 'api_version': 3}
    with pytest.raises(logic.NotAuthorized):
        helpers.call_auth("bulk_update_delete", test_context,
                          datasets=[ds1, ds2],
                          org_id=owner_org["id"])

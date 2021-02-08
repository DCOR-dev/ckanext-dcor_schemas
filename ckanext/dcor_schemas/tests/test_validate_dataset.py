import pathlib

import pytest

import ckan.logic as logic
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers

from .helper_methods import make_dataset

data_path = pathlib.Path(__file__).parent / "data"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_authors_is_csv():
    """author list "authors" is CSV"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False, 'user': user['name']}

    ds, _ = make_dataset(create_context1, owner_org, with_resource=True,
                         activate=True,
                         authors="Peter Pan,Ben Elf,  Buddy Holly")  # [sic!]
    dataset = helpers.call_action("package_show",
                                  id=ds["id"],
                                  )
    assert dataset["authors"] == "Peter Pan, Ben Elf, Buddy Holly"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_authors_mandatory():
    """force user to select authors"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False, 'user': user['name']}

    with pytest.raises(logic.ValidationError) as e:
        make_dataset(create_context1, owner_org, with_resource=False,
                     activate=False, authors="")
    assert "'authors': ['Missing value']" in str(e.value)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_doi_remove_url():
    """parse DOI field (remove URL part)"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False, 'user': user['name']}

    ds, _ = make_dataset(create_context1, owner_org, with_resource=True,
                         activate=True,
                         doi="https://doi.org/10.1371/journal.pone.0088458"
                         )
    dataset = helpers.call_action("package_show",
                                  id=ds["id"],
                                  )
    assert dataset["doi"] == "10.1371/journal.pone.0088458"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_draft_no_resources():
    """a dataset without resources is considered to be a draft"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False, 'user': user['name']}

    ds = make_dataset(create_context, owner_org, with_resource=False,
                      activate=True)
    assert ds["state"] == "draft"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_license_id_mandatory():
    """force user to select license_id"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False, 'user': user['name']}

    with pytest.raises(logic.ValidationError) as e:
        make_dataset(create_context1, owner_org, with_resource=False,
                     activate=False, license_id="")
    assert "Please choose a license_id" in str(e.value)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_license_restrict_cc():
    """restrict to basic CC licenses"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False, 'user': user['name']}

    with pytest.raises(logic.ValidationError) as e:
        make_dataset(create_context1, owner_org, with_resource=False,
                     activate=False, license_id="CC-BY-NE-4.0")
    assert "Please choose a license_id" in str(e.value)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_name_slug():
    """automatically generate dataset name (slug) using random characters"""
    user = factories.User()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False, 'user': user['name']}
    ds1 = make_dataset(create_context1, owner_org, with_resource=False,
                       activate=False, name="ignored")
    assert ds1["name"] != "ignored"

    create_context2 = {'ignore_auth': False, 'user': user['name']}
    ds2 = make_dataset(create_context2, owner_org, with_resource=False,
                       activate=False, name="ignored")
    assert ds2["name"] != ds1["name"]


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_dataset_name_slug_no_admin():
    """not automatically generate dataset name (slug) for admins"""
    admin = factories.Sysadmin()
    owner_org = factories.Organization(users=[{
        'name': admin['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    # create 1st dataset
    create_context1 = {'ignore_auth': False, 'user': admin['name']}
    ds1 = make_dataset(create_context1, owner_org, with_resource=False,
                       activate=False, name="ignored")
    assert ds1["name"] == "ignored"

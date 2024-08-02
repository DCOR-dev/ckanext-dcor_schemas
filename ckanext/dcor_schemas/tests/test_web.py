import pathlib
import pytest

import ckan.tests.factories as factories

from dcor_shared.testing import make_dataset


data_path = pathlib.Path(__file__).parent / "data"


def test_status(app):
    app.get("/api/3/action/status_show",
            status=200)


@pytest.mark.parametrize("url", ["/dataset",
                                 "/group",
                                 "/organization",
                                 ])
def test_homepage(url, app):
    user = factories.UserWithToken()
    app.get(url,
            params={u"id": user[u"id"]},
            headers={u"authorization": user["token"]},
            status=200)


def test_homepage_bad_link(app):
    """this is a negative test"""
    app.get("/bad_link", status=404)


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
def test_login_and_browse_to_dataset_new_fails(app):
    """We disabled dataset creation with #20"""
    user = factories.UserWithToken()

    # assert: try to access /dataset
    app.get("/dataset/new",
            params={u"id": user[u"id"]},
            headers={u"authorization": user["token"]},
            status=403,
            )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
@pytest.mark.parametrize("url", ["/dataset",
                                 "/group",
                                 "/group/new",
                                 "/organization",
                                 "/organization/new",
                                 ])
def test_login_and_browse_to_main_locations(url, app):
    user = factories.UserWithToken()

    # assert: try to access /dataset
    app.get(url,
            params={u"id": user[u"id"]},
            headers={u"authorization": user["token"]},
            status=200,
            )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
def test_login_and_go_to_dataset_edit_page(app, create_with_upload):
    user = factories.UserWithToken()

    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    # create a dataset
    ds_dict, _ = make_dataset(
        create_context, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True)

    app.get("/dataset/edit/" + ds_dict["id"],
            params={u"id": user[u"id"]},
            headers={u"authorization": user["token"]},
            status=200
            )


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
def test_login_and_go_to_dataset_edit_page_and_view_license_options(
        app, create_with_upload):
    """Check whether the license options are correct"""
    user = factories.UserWithToken()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    # create a dataset
    ds_dict, _ = make_dataset(
        create_context, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True, license_id="CC-BY-4.0")

    # get the dataset page
    resp = app.get("/dataset/edit/" + ds_dict["id"],
                   params={u"id": user[u"id"]},
                   headers={u"authorization": user["token"]},
                   status=200
                   )
    available_licenses_strings = [
        '<option value="CC-BY-4.0" selected="selected">'
        + 'Creative Commons Attribution 4.0</option>',
        '<option value="CC0-1.0" >'
        + 'Creative Commons Public Domain Dedication</option>',
    ]
    for option in available_licenses_strings:
        assert option in resp.body

    hidden_license_strings = [
        "CC-BY-SA_4.0",
        "CC-BY-NC-4.0",
        "Creative Commons Attribution Share-Alike 4.0",
        "Creative Commons Attribution-NonCommercial 4.0",
    ]
    for bad in hidden_license_strings:
        assert bad not in resp.body


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas')
@pytest.mark.usefixtures('clean_db', 'with_request_context')
def test_resource_view_references(app, create_with_upload):
    """Test whether the references links render correctly"""
    user = factories.UserWithToken()
    owner_org = factories.Organization(users=[{
        'name': user['id'],
        'capacity': 'admin'
    }])
    # Note: `call_action` bypasses authorization!
    create_context = {'ignore_auth': False,
                      'user': user['name'], 'api_version': 3}
    # create a dataset
    references = [
        "https://dx.doi.org/10.1186/s12859-020-03553-y",
        "https://arxiv.org/abs/1507.00466",
        "https://www.biorxiv.org/content/10.1101/862227v2.full.pdf+html",
        "https://dc.readthedocs.io/en/latest/",
    ]
    ds_dict, _ = make_dataset(
        create_context, owner_org,
        create_with_upload=create_with_upload,
        resource_path=data_path / "calibration_beads_47.rtdc",
        activate=True,
        references=",".join(references))

    # get the dataset page
    resp = app.get("/dataset/" + ds_dict["id"],
                   params={u"id": user[u"id"]},
                   headers={u"authorization": user["token"]},
                   status=200
                   )
    rendered_refs = [
        ["https://doi.org/10.1186/s12859-020-03553-y",
         "doi:10.1186/s12859-020-03553-y"],
        ["https://arxiv.org/abs/1507.00466",
         "arXiv:1507.00466"],
        ["https://biorxiv.org/content/10.1101/862227v2",
         "bioRxiv:10.1101/862227v2"],
        ["https://dc.readthedocs.io/en/latest/",
         "https://dc.readthedocs.io/en/latest/"]
    ]

    # make sure the links render correctly
    for link, text in rendered_refs:
        href = '<a href="{}">{}</a>'.format(link, text)
        assert resp.body.count(href)

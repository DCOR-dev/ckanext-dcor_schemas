import pytest

import ckan.model as model
import ckan.tests.factories as factories
import ckan.tests.helpers as helpers


def test_homepage(app):
    resp = app.get("/dataset")
    assert resp.status == "200 OK"


def test_homepage_bad_link(app):
    """this is a negative test"""
    resp = app.get("/bad_link")
    assert resp.status == "404 NOT FOUND"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dcor_theme')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_and_browse_to_circle(app):
    user = factories.User()

    # taken from ckanext/example_iapitoken/tests/test_plugin.py
    data = helpers.call_action(
        u"api_token_create",
        context={u"model": model, u"user": user[u"name"]},
        user=user[u"name"],
        name=u"token-name",
    )

    # assert: try to access /dataset
    resp = app.get("/organization",
                   params={u"id": user[u"id"]},
                   headers={u"authorization": data["token"]},
                   )
    assert resp.status == "200 OK"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dcor_theme')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_and_browse_to_circle_creation_page(app):
    user = factories.User()

    # taken from ckanext/example_iapitoken/tests/test_plugin.py
    data = helpers.call_action(
        u"api_token_create",
        context={u"model": model, u"user": user[u"name"]},
        user=user[u"name"],
        name=u"token-name",
    )

    # assert: try to access /dataset
    resp = app.get("/organization/new",
                   params={u"id": user[u"id"]},
                   headers={u"authorization": data["token"]},
                   )
    assert resp.status == "200 OK"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dcor_theme')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_and_browse_to_collection(app):
    user = factories.User()

    # taken from ckanext/example_iapitoken/tests/test_plugin.py
    data = helpers.call_action(
        u"api_token_create",
        context={u"model": model, u"user": user[u"name"]},
        user=user[u"name"],
        name=u"token-name",
    )

    # assert: try to access /dataset
    resp = app.get("/group",
                   params={u"id": user[u"id"]},
                   headers={u"authorization": data["token"]},
                   )
    assert resp.status == "200 OK"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dcor_theme')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_and_browse_to_collection_creation_page(app):
    user = factories.User()

    # taken from ckanext/example_iapitoken/tests/test_plugin.py
    data = helpers.call_action(
        u"api_token_create",
        context={u"model": model, u"user": user[u"name"]},
        user=user[u"name"],
        name=u"token-name",
    )

    # assert: try to access /dataset
    resp = app.get("/group/new",
                   params={u"id": user[u"id"]},
                   headers={u"authorization": data["token"]},
                   )
    assert resp.status == "200 OK"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dcor_theme')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_and_browse_to_dataset(app):
    user = factories.User()

    # taken from ckanext/example_iapitoken/tests/test_plugin.py
    data = helpers.call_action(
        u"api_token_create",
        context={u"model": model, u"user": user[u"name"]},
        user=user[u"name"],
        name=u"token-name",
    )

    # assert: try to access /dataset
    resp = app.get("/dataset",
                   params={u"id": user[u"id"]},
                   headers={u"authorization": data["token"]},
                   )
    assert resp.status == "200 OK"


@pytest.mark.ckan_config('ckan.plugins', 'dcor_schemas dcor_theme')
@pytest.mark.usefixtures('clean_db', 'with_plugins', 'with_request_context')
def test_login_and_browse_to_dataset_creation_page(app):
    user = factories.User()

    # taken from ckanext/example_iapitoken/tests/test_plugin.py
    data = helpers.call_action(
        u"api_token_create",
        context={u"model": model, u"user": user[u"name"]},
        user=user[u"name"],
        name=u"token-name",
    )

    # assert: try to access /dataset
    resp = app.get("/dataset/new",
                   params={u"id": user[u"id"]},
                   headers={u"authorization": data["token"]},
                   )
    assert resp.status == "200 OK"

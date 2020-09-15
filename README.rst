ckanext-dcor_schemas
====================

This module introduces/lifts restrictions (authorization) for the management
of data and meta data on DCOR. The corresponding UI elements are modified
accordingly:

- Authorization (auth.py)

  - allow all logged-in users to create datasets, labs, and collections
  - do not allow deleting datasets or resources unless they are drafts
  - allow purging of deleted datasets
  - do not allow adding resources to active datasets
  - do not allow bulk_update_delete (e.g. datasets by organization admins)
  - dataset: do not allow switching to a more restrictive license
  - dataset: do not allow changing the name (slug)
  - resource: only allow changing the "description"
  - Do not allow uploading resources with the same name (ckanext-dcor_depot)
  - Allow adding resources up to 3h after creating dataset
  - Do not allow setting a resource id when uploading

- Permissions (plugin.py)

  - Allow a user A to see user B's private dataset if the private dataset
    is in a group that user A is a member of.

- Validation (validate.py)

  - Do not allow setting a different resource name when uploading
  - Do not allow weird characters in resource names
  - Restrict to basic CC licenses
  - Author list "authors" is CSV
  - Parse DOI field (remove URL part)
  - Automatically generate dataset name (slug) using random characters
    if necessary (does not apply to admins)
  - restrict upload data extensions to .rtdc, .csv, .tsv, .pdf, .txt, .png,
    .jpg, .tif, .py, .ipynb
  - Force user to select a license
  - Do not allow non-admins to set the visibility of a public dataset to private
  - Configuration metadata (using `dclab.dfn.config_funcs`)
  - A dataset is considered to be a draft when it does not contain resources
    (validate.state)
  - Allow to delete draft datasets

- UI Dataset:

  - hide "add new resource" button in ``templates/package/resources.html``
  - remove ``url``, ``version``, ``author``, ``author_email``, ``maintainer``,
    ``maintainer_email`` (``templates/package/snippets/package_metadata_fields.html``)
  - add field ``authors`` (csv list)
  - add field ``doi`` (validator parses URLs)
  - add field ``references`` (parses arxiv, bioRxiv, DOI, links)
  - add CC license file ``licenses.json`` (only show less restrictive licenses
    when editing the dataset)
  - hide name (slug) editing form
  - dataset visibility is public by default

- UI Organization:

  - remove "Delete" button in bulk view

- UI Resource:

  - Resource: remove "URL" button when creating a resource (only upload makes sense)
    (``fanstatic/dcor_schemas_data_upload.js``
    and ``templates/package/snippets/resource_form.html``)
  - Add metadata key ``sha256`` (and protect it with
    ``IResourceController.before_update``)
  - Do not show variables these variables (because they are redundant):
    ['last modified', 'revision id', 'url type', 'state', 'on same domain']
    (``templates/package/resource_read.html``)
  - Show DC config data via "toggle-more"

- Background jobs:

  - set the mimetype for each dataset
  - populate "dc:sec:key" metadata for each DC dataset
  - generates sha256 hash upon resource creation


Installation
------------
Simply run

::

    pip install ckanext-dcor_schemas

In the configuration file ckan.ini:

::
    
    ckan.plugins = [...] dcor_schemas
    ckan.extra_resource_fields = sha256

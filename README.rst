ckanext-dcor_schemas
====================

|PyPI Version| |Build Status| |Coverage Status|

This module introduces/lifts restrictions (authorization) for the management
of data and meta data on DCOR. The corresponding UI elements are modified
accordingly:

- Authorization (auth.py)

  - datasets: do not allow deleting datasets unless they are drafts
  - datasets: allow purging of deleted datasets
  - datasets: do not allow switching to a more restrictive license
  - datasets: do not allow changing the name (slug)
  - datasets: do not allow adding resources to non-draft datasets
  - datasets: do not allow to set the visibility of a public dataset to private
  - datasets: do not allow uploading datasets via the web interface
  - organization: do not allow bulk_update_delete (e.g. datasets by organization admins)
  - resources: do not allow deleting resources unless they are drafts
  - resources: only allow changing the "description"
  - resources: do not allow setting a resource id when uploading
  - user: allow all logged-in users to create datasets, circles, and collections

- Validation (validate.py)

  - datasets: force user to select authors
  - datasets: author list "authors" is CSV
  - datasets: parse DOI field (remove URL part)
  - datasets: force user to select a license
  - datasets: restrict to basic CC licenses
  - datasets: automatically generate dataset name (slug) using random characters
    if necessary (does not apply to admins)
  - datasets: a dataset without resources is considered to be a draft;
    it's state cannot be set to "active"
  - datasets: the state of a dataset that does not contain at least one
    valid .rtdc resource cannot be set to "active"
  - resources: do not allow uploading resources with the same name
    for a dataset (important for ckanext-dcor_depot)
  - resources: make sure the resource name matches the file name of the
    upload; this is actually implemented in plugin.before_create
    (IResourceController) and not in validate.py
  - resources: custom resource name is overridden during upload
  - resources: do not allow weird characters in resource names
  - resources: restrict upload data extensions to .'.rtdc', '.ini', '.csv',
    '.tsv', '.pdf', '.txt', '.jpg', '.png', '.tif', '.py', '.ipynb', '.poly',
    '.sof', '.so2'
  - resources: configuration metadata (using `dclab.dfn.config_funcs`)
  - resources: 's3_available' and 's3_url' for identifying objects that
    are available on S3 and for downloading public datasets.

- IPermissionLabels (plugin.py)

  - Allow a user A to see user B's private dataset if the private dataset
    is in a group that user A is a member of.

- UI Dataset:

  - hide "add new resource" button in ``templates/package/resources.html``
  - add field ``authors`` (csv list)
  - add field ``doi`` (validator parses URLs)
  - add field ``references`` (parses arxiv, bioRxiv, DOI, links)
  - add CC license file ``licenses.json`` (only show less restrictive licenses
    when editing the dataset)

- UI Organization:

  - remove "Delete" button in bulk view

- UI Resource:

  - Do not show these variables (because they are redundant):
    ['last modified', 'revision id', 'url type', 'state', 'on same domain']
    (``templates/package/resource_read.html``)
  - Show DC config data via "toggle-more"
  - Add supplementary resource schema via json files located in
    `dcor_schemas/resource_schema_supplements`

- Background jobs:

  - set the mimetype for each dataset
  - populate "dc:sec:key" metadata for each DC dataset
  - generates sha256 hash upon resource creation
  - populate etag resource property from S3 storage upon resource creation

- Configuration keywords:

  - the ``ckanext.dcor_schemas.allow_content_listing_for_anon`` boolean
    parameter can be set to False to prevent anonymous users to see
    circles, colletions, and other content.
  - the ``ckanext.dcor_schemas.allow_public_datasets`` boolean parameter
    can be used to disable the creation of public datasets (e.g. for DCOR-med).
  - the ``ckanext.dcor_schemas.json_resource_schema_dir`` parameter
    can be used to specify a directory containing .json files that
    define the supplementary resource schema. The default is
    ``package`` which means that the supplementary resource schema of
    this extension is used.

  - These DCOR-wide configuratio options for accessing S3 object storage

    - ``endpoint_url``
    - ``bucket_name``
    - ``access_key_id``
    - ``secret_access_key``
    - ``ssl_verify``

- API extensions:

  - ``resource_upload_s3_urls`` returns a dictionary containing the upload
    URLs (single file or multipart) required for uploading a new resource
    directly to S3
  - ``resource_schema_supplements`` returns a dictionary of the
    current supplementary resource schema
  - ``supported_resource_suffixes`` returns a list of supported
    resource suffixes

- CLI:

  - CKAN command `list-circles` returns the list of DCOR circles
  - CKAN command `list-collections` returns the list of DCOR collections
  - CKAN command `list-group-resources <NAME>` returns the list of resources in
    a DCOR circle or collection
  - CKAN command `list-zombie-users` for users with no datasets and
    no activity for a certain amount of time
  - CKAN command `run-jobs-dcor-schemas` that runs all background
    jobs for all resources (if not already done)
  - CKAN command `dcor-move-dataset-to-circle` for moving a dataset to
    a different circle


Installation
------------
Simply run

::

    pip install ckanext-dcor_schemas

In the configuration file ckan.ini:

::
    
    ckan.plugins = [...] dcor_schemas
    ckan.extra_resource_fields = etag sha256


Testing
-------
If CKAN/DCOR is installed and setup for testing, this extension can
be tested with pytest:

::

    pytest ckanext

Testing can also be done via vagrant in a virtualmachine using the
`dcor-test <https://app.vagrantup.com/paulmueller/boxes/dcor-test/>` image.
Make sure that `vagrant` and `virtualbox` are installed and run the
following commands in the root of this repository:

::

    # Setup virtual machine using `Vagrantfile`
    vagrant up
    # Run the tests
    vagrant ssh -- sudo bash /testing/vagrant-run-tests.sh


.. |PyPI Version| image:: https://img.shields.io/pypi/v/ckanext.dcor_schemas.svg
   :target: https://pypi.python.org/pypi/ckanext.dcor_schemas
.. |Build Status| image:: https://img.shields.io/github/actions/workflow/status/DCOR-dev/ckanext-dcor_schemas/check.yml
   :target: https://github.com/DCOR-dev/ckanext-dcor_schemas/actions?query=workflow%3AChecks
.. |Coverage Status| image:: https://img.shields.io/codecov/c/github/DCOR-dev/ckanext-dcor_schemas
   :target: https://codecov.io/gh/DCOR-dev/ckanext-dcor_schemas

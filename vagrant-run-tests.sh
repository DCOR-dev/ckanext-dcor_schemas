set -e
set -x
# Set CKAN_INI to testing
export CKAN_INI=/etc/ckan/default/test-dcor.ini
# Go to the directory of this script
cd "$(dirname "${BASH_SOURCE[0]}")"
# Source the CKAN environment
source /usr/lib/ckan/default/bin/activate
# Update all DCOR extensions
dcor update
# Install the current package in editable mode for testing
pip install -e .
# run tests
coverage run -m pytest -p no:warnings ckanext
# submit code coverage
codecov

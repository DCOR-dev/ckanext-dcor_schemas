set -e
set -x
# Set CKAN_INI to testing
export CKAN_INI=/etc/ckan/default/test-dcor.ini
# Go to the directory of this script
cd "$(dirname "${BASH_SOURCE[0]}")"
# Install the package in editable mode for testing
source /usr/lib/ckan/default/bin/activate
pip install -e .
# run tests
coverage run -m pytest -p no:warnings ckanext
codecov

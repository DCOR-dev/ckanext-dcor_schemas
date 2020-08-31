import ckan.model as model
import ckan.plugins.toolkit as toolkit


def get_reference_dict(value):
    refs = [a.strip() for a in value.split(",") if a.strip()]
    rdict = {"arxiv": [],
             "biorxiv": [],
             "links": [],
             "dois": [],
             }

    for r in refs:
        if r.startswith("arxiv:"):
            rdict["arxiv"].append(r.split(":")[1])
        elif r.startswith("doi:"):
            rdict["dois"].append(r.split(":")[1])
        elif r.startswith("bioRxiv:"):
            rdict["biorxiv"].append(r.split(":")[1])
        else:
            rdict["links"].append(r)
    return rdict


def get_user_name(user_id):
    usr = toolkit.get_action('user_show')(data_dict={'id': user_id})
    return usr["name"], usr["display_name"]


def get_valid_licenses(license_id):
    lr = {  # lists licenses according to strictness
        "CC0-1.0": 0,
        "CC-BY-4.0": 1,
        "CC-BY-SA-4.0": 2,
        "CC-BY-NC-4.0": 2,
        "none": 3,
    }
    res = lr.get(license_id, 0)
    allowed = [ll for ll in lr if lr[ll] < res]
    return list(set(allowed + [license_id]))


def license_options(existing_license_id="none"):
    '''Returns [(l.title, l.id), ...] for the licenses configured to be
    offered. Always includes the existing_license_id, if supplied.

    DCOR edit: prohibit license downgrade
    '''
    register = model.Package.get_license_register()
    sorted_licenses = sorted(register.values(), key=lambda x: x.title)
    license_ids = [lic.id for lic in sorted_licenses]
    allowed = get_valid_licenses(existing_license_id)
    license_ids = [ll for ll in license_ids if ll in allowed]
    if existing_license_id and existing_license_id not in license_ids:
        license_ids.insert(0, existing_license_id)
    return [
        (license_id,
         register[license_id].title if license_id in register else license_id)
        for license_id in license_ids]
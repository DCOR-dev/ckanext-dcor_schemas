from ckan.common import asbool, config
from ckan.lib import mailer


def notify_user_created(sender, **kwargs):
    recipient_email = config.get("email_to")
    site = config.get("ckan.site_title")
    url = config.get("ckan.site_url")
    user = kwargs.get('user')
    if asbool(config.get("ckanext.dcor_schemas.notify_user_create")):
        if recipient_email and recipient_email.count("@"):
            mailer.mail_recipient(
                recipient_name=f"{site} Maintainer",
                recipient_email=recipient_email,
                subject=f"New user '{user.name}' at {site} ({url})",
                body=f"""A new user was created at {site} ({url}).

Name: {user.fullname}
Handle: {user.name}
Email: {user.email}
About: {(user.about or '')[:20]}...
""",
            )

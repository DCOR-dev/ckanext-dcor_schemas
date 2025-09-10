from ckan.lib import mailer
from dcor_shared import get_ckan_config_option


def notify_user_created(sender, **kwargs):
    recipient_email = get_ckan_config_option("email_to")
    site = get_ckan_config_option("ckan.site_title")
    url = get_ckan_config_option("ckan.site_url")
    user_dict = kwargs.get('user')
    if recipient_email and recipient_email.count("@"):
        mailer.mail_recipient(
            recipient_name=f"{site} Maintainer",
            recipient_email=recipient_email,
            subject=f"New user at {site} ({url})",
            body=f"""A new user was created at {site} ({url}).

Name: {user_dict.get('fullname')}
Handle: {user_dict.get('name')}
Email: {user_dict.get('email')}
ID: {user_dict.get('id')}
Time: {user_dict.get('created')}
About: {user_dict.get('about', '')[:20]}...
""",
        )

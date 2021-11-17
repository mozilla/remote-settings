from .signer.events import ReviewApproved, ReviewRejected, ReviewRequested


def includeme(config):
    config.include("kinto_remote_settings.changes")
    config.include("kinto_remote_settings.signer")

    try:
        from kinto_emailer import send_notification

        config.add_subscriber(send_notification, ReviewRequested)
        config.add_subscriber(send_notification, ReviewApproved)
        config.add_subscriber(send_notification, ReviewRejected)
    except ImportError:
        pass

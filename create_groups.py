import argparse
from functools import partial

from kinto_http import Client


DEFAULT_SERVER = 'http://localhost:8888/v1'
DEFAULT_AUTH = 'user:pass'
DEFAULT_EDITOR_AUTH = 'editor:pass'
DEFAULT_REVIEWER_AUTH = 'reviewer:pass'
DEFAULT_BUCKET = 'staging'


def _get_args():
    parser = argparse.ArgumentParser(description='End-to-end signing test')

    parser.add_argument('--server', help='Kinto Server',
                        type=str, default=DEFAULT_SERVER)

    parser.add_argument('--auth', help='Admin Authentication',
                        type=str, default=DEFAULT_AUTH)

    parser.add_argument('--bucket', help='Bucket',
                        type=str, default=DEFAULT_BUCKET)

    parser.add_argument('--editor-auth', help='Editor Authentication',
                        type=str, default=DEFAULT_EDITOR_AUTH)

    parser.add_argument('--reviewer-auth', help='Reviewer Authentication',
                        type=str, default=DEFAULT_REVIEWER_AUTH)

    return parser.parse_args()


def main():
    args = _get_args()

    # why do I have to do all of this just to set up auth...
    def _auth(req, user='', password=''):
        req.prepare_auth((user, password))
        return req

    if args.auth is not None:
        user, password = args.auth.split(':')
        args.auth = partial(_auth, user=user, password=password)

    if args.editor_auth is not None:
        user, password = args.editor_auth.split(':')
        args.editor_auth = partial(_auth, user=user, password=password)

    if args.reviewer_auth is not None:
        user, password = args.reviewer_auth.split(':')
        args.reviewer_auth = partial(_auth, user=user, password=password)

    admin_client = Client(server_url=args.server, auth=args.auth,
                          bucket=args.bucket)
    editor_client = Client(server_url=args.server, auth=args.editor_auth)
    reviewer_client = Client(server_url=args.server, auth=args.reviewer_auth)

    # 0. initialize source bucket/collection (if necessary)
    print("Create bucket: %s" % args.bucket)
    admin_client.create_bucket(if_not_exists=True)

    print("Get editor's user id")
    editor_id = editor_client.server_info()['user']['id']

    print("Get reviewer's user id")
    reviewer_id = reviewer_client.server_info()['user']['id']

    print("Create editors group")
    admin_client.create_group('editors', data={'members': [editor_id]}, if_not_exists=True)

    print("Create reviewers group")
    admin_client.create_group('reviewers', data={'members': [reviewer_id]}, if_not_exists=True)


if __name__ == '__main__':
    main()

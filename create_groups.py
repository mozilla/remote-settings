import argparse

from kinto_http import Client


DEFAULT_SERVER = 'http://localhost:8888/v1'
DEFAULT_AUTH = 'user:pass'
DEFAULT_EDITOR_AUTH = 'editor:pass'
DEFAULT_REVIEWER_AUTH = 'reviewer:pass'
DEFAULT_BUCKET = 'staging'


def _get_args():
    parser = argparse.ArgumentParser(description='Create workflow groups')

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

    print("Get editor's user id")
    editor_client = Client(server_url=args.server,
                           auth=tuple(args.editor_auth.split(':')))
    editor_id = editor_client.server_info()['user']['id']

    print("Get reviewer's user id")
    reviewer_client = Client(server_url=args.server,
                             auth=tuple(args.reviewer_auth.split(':')))
    reviewer_id = reviewer_client.server_info()['user']['id']

    print("Create signoff workflow groups")
    admin_client = Client(server_url=args.server,
                          auth=tuple(args.auth.split(':')),
                          bucket=args.bucket)

    print("Create/update editors group")
    editors_group = admin_client.create_group('editors', data={'members': []}, if_not_exists=True)
    editors_group['data']['members'] = editors_group['data']['members'] + [editor_id]
    admin_client.update_group('editors', editors_group['data'], safe=True)

    print("Create/update reviewers group")
    reviewers_group = admin_client.create_group('reviewers', data={'members': []}, if_not_exists=True)
    reviewers_group['data']['members'] = reviewers_group['data']['members'] + [reviewer_id]
    admin_client.update_group('reviewers', data=reviewers_group['data'], safe=True)


if __name__ == '__main__':
    main()

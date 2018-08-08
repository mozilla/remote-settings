#!/bin/bash

# Fail if any command returns non-zero
# Show executed commands
set -e -x

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SERVER="${SERVER:-http://localhost:8888/v1}"
MAILFILESERVER="${MAILFILESERVER:-http://localhost:9999}"

AUTH="${AUTH:-user:pass}"
EDITOR_AUTH="${EDITOR_AUTH:-editor:pass}"
REVIEWER_AUTH="${REVIEWER_AUTH:-reviewer:pass}"

# Create Kinto accounts
echo '{"data": {"password": "pass"}}' | http --check-status PUT $SERVER/accounts/user
echo '{"data": {"password": "pass"}}' | http --check-status PUT $SERVER/accounts/editor
echo '{"data": {"password": "pass"}}' | http --check-status PUT $SERVER/accounts/reviewer

http --check-status PUT $SERVER/buckets/blog --auth $AUTH
http --check-status PUT $SERVER/buckets/blog/collections/articles --auth $AUTH
# Create preview and destination buckets explicitly (see Kinto/kinto-signer#155)
http --check-status PUT $SERVER/buckets/blocklists --auth $AUTH
http --check-status PUT $SERVER/buckets/blocklists-preview --auth $AUTH

http --check-status $SERVER/__heartbeat__
http --check-status $SERVER/__api__ | grep "/buckets/monitor/collections/changes/records"

# kinto.plugins.history
http --check-status GET $SERVER/buckets/blog/history --auth $AUTH | grep '"articles"'

# kinto-attachment test
# New record.
http --check-status --form POST $SERVER/buckets/blog/collections/articles/records/80ec9929-6896-4022-8443-3da4f5353f47/attachment attachment@kinto-logo.svg --auth $AUTH
# Existing record.
echo '{"data": {"type": "logo"}}' | http --check-status PUT $SERVER/buckets/blog/collections/articles/records/logo --auth $AUTH
http --check-status --form POST $SERVER/buckets/blog/collections/articles/records/logo/attachment attachment@kinto-logo.svg --auth $AUTH

# kinto-signer test
python $DIR/e2e.py --server=$SERVER --auth=$AUTH --editor-auth=$EDITOR_AUTH --reviewer-auth=$REVIEWER_AUTH --source-bucket=source --source-col=source
python $DIR/create_groups.py --server=$SERVER --bucket=source --auth="$AUTH" --editor-auth="$EDITOR_AUTH" --reviewer-auth="$REVIEWER_AUTH"

# kinto-changes
http --check-status $SERVER/buckets/monitor/collections/changes/records | grep '"destination"'

# kinto-admin
http --check-status -h "$SERVER/admin/"
http --check-status -h "$SERVER/admin/index.html"

# kinto-amo
APPID="\{ec8030f7-c20a-464f-9b0e-13a3a9e97384\}"
http --check-status $SERVER/blocklist/3/$APPID/46.0/
echo '{"permissions": {"write": ["system.Authenticated"]}}' | http PUT $SERVER/buckets/staging --auth="$AUTH"

python $DIR/create_groups.py --server=$SERVER --bucket=staging --auth="$AUTH" --editor-auth="$EDITOR_AUTH" --reviewer-auth="$REVIEWER_AUTH"
# 1. Add a few records
pwd # TEMP
ls -l  # TEMP
kinto-wizard load amo-blocklist.yaml --server "$SERVER" --auth="$AUTH" --bucket staging

# 2. Ask for a review
echo '{"data": {"status": "to-review"}}' | http --check-status PATCH $SERVER/buckets/staging/collections/certificates --auth "$EDITOR_AUTH"
echo '{"data": {"status": "to-review"}}' | http --check-status PATCH $SERVER/buckets/staging/collections/gfx --auth "$EDITOR_AUTH"
echo '{"data": {"status": "to-review"}}' | http --check-status PATCH $SERVER/buckets/staging/collections/plugins --auth "$EDITOR_AUTH"
echo '{"data": {"status": "to-review"}}' | http --check-status PATCH $SERVER/buckets/staging/collections/addons --auth "$EDITOR_AUTH"

# 3. Validate the review
echo '{"data": {"status": "to-sign"}}' | http --check-status PATCH $SERVER/buckets/staging/collections/certificates --auth "$REVIEWER_AUTH"
echo '{"data": {"status": "to-sign"}}' | http --check-status PATCH $SERVER/buckets/staging/collections/gfx --auth "$REVIEWER_AUTH"
echo '{"data": {"status": "to-sign"}}' | http --check-status PATCH $SERVER/buckets/staging/collections/plugins --auth "$REVIEWER_AUTH"
echo '{"data": {"status": "to-sign"}}' | http --check-status PATCH $SERVER/buckets/staging/collections/addons --auth "$REVIEWER_AUTH"


# Preview XML was published during review
http --check-status $SERVER/preview/3/$APPID/46.0/ | grep 'youtube'
# Final XML is identical to production
http --check-status $SERVER/blocklist/3/$APPID/46.0/ | grep 'youtube'
# xml-verifier blocked/blocklists.xml $SERVER/blocklist/3/$APPID/46.0/


# Expected monitored changes
http --check-status $SERVER/buckets/monitor/collections/changes/records | grep '"blocklists-preview"'
http --check-status $SERVER/buckets/monitor/collections/changes/records | grep '"addons"'
http --check-status $SERVER/buckets/monitor/collections/changes/records | grep '"certificates"'
http --check-status $SERVER/buckets/monitor/collections/changes/records | grep '"plugins"'
http --check-status $SERVER/buckets/monitor/collections/changes/records | grep '"gfx"'
# Empty history for preview and signed.
http --check-status GET $SERVER/buckets/blocklists/history --auth $AUTH | grep '\[\]'
http --check-status GET $SERVER/buckets/blocklists-preview/history --auth $AUTH | grep '\[\]'

curl -O https://raw.githubusercontent.com/Kinto/kinto-signer/2.1.0/scripts/validate_signature.py
python validate_signature.py --server=$SERVER --bucket=blocklists --collection=addons
python validate_signature.py --server=$SERVER --bucket=blocklists --collection=certificates
python validate_signature.py --server=$SERVER --bucket=blocklists --collection=plugins
python validate_signature.py --server=$SERVER --bucket=blocklists --collection=gfx

#
# Emailer
#
echo '{"data": {
  "kinto-emailer": {
    "hooks": [{
      "event": "kinto_signer.events.ReviewRequested",
      "subject": "{user_id} requested review on {bucket_id}/{collection_id}.",
      "template": "Review changes at {root_url}admin/#/buckets/{bucket_id}/collections/{collection_id}/records",
      "recipients": ["me@you.com", "/buckets/source/groups/reviewers"]
    }]
  }
}}' | http PATCH $SERVER/buckets/source --auth="$AUTH"

echo '{"data": {"status": "to-review"}}' | http PATCH $SERVER/buckets/source/collections/source --auth="$EDITOR_AUTH"

cat mail/*.eml | grep "Subject: account"
cat mail/*.eml | grep "To: me@you.com"


# END OF THE TEST
# If you made it here, that means all the smoke tests above did not fail.
# Party!

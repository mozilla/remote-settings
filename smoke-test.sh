# Fail if any command returns non-zero
# Show executed commands
set -e -x

source .venv/bin/activate
pip install httpie

SERVER=http://localhost:8888/v1

http --check-status PUT $SERVER/buckets/source --auth user:pass
http --check-status PUT $SERVER/buckets/source/collections/source --auth user:pass

http --check-status $SERVER/__heartbeat__

# kinto-attachment test
curl -O "http://kinto.readthedocs.io/en/stable/_images/kinto-logo.png"

http --check-status --form POST $SERVER/buckets/source/collections/source/records/80ec9929-6896-4022-8443-3da4f5353f47/attachment attachment@kinto-logo.png --auth user:pass

# kinto-signer test
http --check-status PUT $SERVER/buckets/source/collections/source/records/xxyz --auth user:pass
echo '{"data": {"status":"to-sign"}}' | http --check-status PATCH $SERVER/buckets/source/collections/source --auth user:pass
http --check-status $SERVER/buckets/destination/collections/destination | grep '"signature"'
http --check-status $SERVER/buckets/destination/collections/destination/records | grep '"xxyz"'

# kinto-changes
http --check-status $SERVER/buckets/monitor/collections/changes/records | grep '"source"'

# kinto-admin
http --check-status -h $SERVER/admin/
http --check-status -h $SERVER/admin/bundle.js
http --check-status -h $SERVER/admin/styles.css

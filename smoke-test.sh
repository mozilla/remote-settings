# Fail if any command returns non-zero
# Show executed commands
set -e -x

source .venv/bin/activate
pip install httpie

http --check-status PUT http://localhost:8888/v1/buckets/source Authorization:"Basic dXNlcjpwYXNz"
http --check-status PUT http://localhost:8888/v1/buckets/source/collections/source Authorization:"Basic dXNlcjpwYXNz"

http --check-status "http://localhost:8888/v1/__heartbeat__"

# kinto-attachment test
curl -O "http://kinto.readthedocs.io/en/stable/_images/kinto-logo.png"

http --check-status --form POST http://localhost:8888/v1/buckets/source/collections/source/records/80ec9929-6896-4022-8443-3da4f5353f47/attachment Authorization:"Basic dXNlcjpwYXNz" attachment@kinto-logo.png

# kinto-signer test
http --check-status PUT http://localhost:8888/v1/buckets/source/collections/source/records/xxyz Authorization:"Basic dXNlcjpwYXNz"
echo '{"data": {"status":"to-sign"}}' | http --check-status PATCH http://localhost:8888/v1/buckets/source/collections/source Authorization:"Basic dXNlcjpwYXNz"
http --check-status http://localhost:8888/v1/buckets/destination/collections/destination | grep '"signature"'
http --check-status http://localhost:8888/v1/buckets/destination/collections/destination/records | grep '"xxyz"'

# kinto-changes
http --check-status http://localhost:8888/v1/buckets/monitor/collections/changes/records | grep '"source"'


# kinto-admin
http --check-status -h http://localhost:8888/v1/admin/
http --check-status -h http://localhost:8888/v1/admin/bundle.js
http --check-status -h http://localhost:8888/v1/admin/styles.css

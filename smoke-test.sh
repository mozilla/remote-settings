# Fail if any command returns non-zero
# Show executed commands
set -e -x

source .venv/bin/activate
pip install httpie

http PUT http://localhost:8888/v1/buckets/source Authorization:"Basic dXNlcjpwYXNz"
http PUT http://localhost:8888/v1/buckets/source/collections/source Authorization:"Basic dXNlcjpwYXNz"

http "http://localhost:8888/v1/__heartbeat__"

# kinto-attachment test
curl -O "http://kinto.readthedocs.io/en/stable/_images/kinto-logo.png"

http POST http://localhost:8888/v1/buckets/source/collections/source/records/abcde/attachment Authorization:"Basic dXNlcjpwYXNz" Content-Type:"multipart/form-data" attachment=@kinto-logo.png

# kinto-signer test
http PUT http://localhost:8888/v1/buckets/source/collections/source/records/xxyz Authorization:"Basic dXNlcjpwYXNz"
echo '{"data": {"status":"to-sign"}}' | http PATCH http://localhost:8888/v1/buckets/source/collections/source Authorization:"Basic dXNlcjpwYXNz"
http http://localhost:8888/v1/buckets/destination/collections/destination | grep '"signature"'
http http://localhost:8888/v1/buckets/destination/collections/destination/records | grep '"xxyz"'

# kinto-changes
http http://localhost:8888/v1/buckets/monitor/collections/changes/records | grep '"source"'

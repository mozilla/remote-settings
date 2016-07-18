# Fail if any command returns non-zero
# Show executed commands
set -e -x

curl --fail -v -X PUT -H "Authorization: Basic dXNlcjpwYXNz" "http://localhost:8888/v1/buckets/source"
curl --fail -v -X PUT -H "Authorization: Basic dXNlcjpwYXNz" "http://localhost:8888/v1/buckets/source/collections/source"

curl --fail -v "http://localhost:8888/v1/__heartbeat__"

# kinto-attachment test
curl -O "http://kinto.readthedocs.io/en/stable/_images/kinto-logo.png"
sleep 1
curl --fail -v -X POST -H "Content-Type: multipart/form-data" -H "Authorization: Basic dXNlcjpwYXNz" -F "attachment=@kinto-logo.png" "http://localhost:8888/v1/buckets/source/collections/source/records/abcde/attachment"

# kinto-signer test
curl --fail -v -X PUT -H "Authorization: Basic dXNlcjpwYXNz" "http://localhost:8888/v1/buckets/source/collections/source/records/xxyz"
curl --fail -v -X PATCH -H "Authorization: Basic dXNlcjpwYXNz"  --header "Content-Type:application/json"  --data '{"data": {"status":"to-sign"}}' "http://localhost:8888/v1/buckets/source/collections/source"
curl "http://localhost:8888/v1/buckets/destination/collections/destination" | grep '"signature"'
curl "http://localhost:8888/v1/buckets/destination/collections/destination/records" | grep '"xxyz"'

# kinto-changes
curl "http://localhost:8888/v1/buckets/monitor/collections/changes/records" | grep '"source"'

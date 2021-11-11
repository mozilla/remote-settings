import unittest

import pytest
from pyramid.exceptions import ConfigurationError

from kinto_remote_settings.signer import utils


class ParseResourcesTest(unittest.TestCase):
    def test_missing_arrow_raises_an_exception(self):
        raw_resources = """
        foo bar
        """
        with pytest.raises(ConfigurationError):
            utils.parse_resources(raw_resources)

    def test_non_local_first_argument_raises_an_exception(self):
        raw_resources = """
        foo -> bar
        bar -> baz
        """
        with pytest.raises(ConfigurationError):
            utils.parse_resources(raw_resources)

    def test_malformed_url_raises_an_exception(self):
        raw_resources = """
        /buckets/sbid/scid -> /buckets/dbid/collections/dcid
        """
        with pytest.raises(ConfigurationError):
            utils.parse_resources(raw_resources)

    def test_outnumbered_urls_raises_an_exception(self):
        raw_resources = (
            "/buckets/sbid/scid -> "
            "/buckets/dbid/collections/dcid -> "
            "/buckets/dbid/collections/dcid -> "
            "/buckets/sbid/scid"
        )
        with pytest.raises(ConfigurationError):
            utils.parse_resources(raw_resources)

    def test_returned_resources_match_the_expected_format(self):
        raw_resources = """
        /buckets/sbid/collections/scid -> /buckets/dbid/collections/dcid
        """
        resources = utils.parse_resources(raw_resources)
        assert resources == {
            "/buckets/sbid/collections/scid": {
                "source": {"bucket": "sbid", "collection": "scid"},
                "destination": {"bucket": "dbid", "collection": "dcid"},
            }
        }

    def test_returned_resources_match_the_legacy_format(self):
        raw_resources = """
        sbid/scid -> dbid/dcid
        """
        resources = utils.parse_resources(raw_resources)
        assert resources == {
            "/buckets/sbid/collections/scid": {
                "source": {"bucket": "sbid", "collection": "scid"},
                "destination": {"bucket": "dbid", "collection": "dcid"},
            }
        }

        raw_resources = """
        sbid/scid ; dbid/dcid
        """
        resources = utils.parse_resources(raw_resources)
        assert resources == {
            "/buckets/sbid/collections/scid": {
                "source": {"bucket": "sbid", "collection": "scid"},
                "destination": {"bucket": "dbid", "collection": "dcid"},
            }
        }

    def test_spaces_are_supported(self):
        raw_resources = """
        /buckets/bid1/collections/scid1 -> /buckets/bid1/collections/dcid1
        /buckets/bid2/collections/scid2 -> /buckets/bid2/collections/dcid2
        """
        resources = utils.parse_resources(raw_resources)
        assert len(resources) == 2
        assert (
            resources["/buckets/bid1/collections/scid1"]["source"]["bucket"] == "bid1"
        )
        assert (
            resources["/buckets/bid2/collections/scid2"]["source"]["bucket"] == "bid2"
        )

    def test_multiple_resources_are_supported(self):
        raw_resources = """
        /buckets/sbid1/collections/scid1 -> /buckets/dbid1/collections/dcid1
        /buckets/sbid2/collections/scid2 -> /buckets/dbid2/collections/dcid2
        """
        resources = utils.parse_resources(raw_resources)
        assert len(resources) == 2

    def test_a_preview_collection_is_supported(self):
        raw_resources = (
            "/buckets/stage/collections/cid -> "
            "/buckets/preview/collections/cid -> "
            "/buckets/prod/collections/cid -> "
        )
        resources = utils.parse_resources(raw_resources)
        assert resources == {
            "/buckets/stage/collections/cid": {
                "source": {"bucket": "stage", "collection": "cid"},
                "preview": {"bucket": "preview", "collection": "cid"},
                "destination": {"bucket": "prod", "collection": "cid"},
            }
        }

    def test_resources_should_be_space_separated(self):
        raw_resources = (
            "/buckets/sbid1/collections/scid -> /buckets/dbid1/collections/dcid,"
            "/buckets/sbid2/collections/scid -> /buckets/dbid2/collections/dcid"
        )
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

        raw_resources = "sbid1/scid -> dbid1/dcid,sbid2/scid -> dbid2/dcid"
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

    def test_resources_must_be_valid_names(self):
        raw_resources = (
            "/buckets/sbi+d1/collections/scid -> /buckets/dbid1/collections/dci,d"
        )
        with self.assertRaises(ConfigurationError) as e:
            utils.parse_resources(raw_resources)
        assert repr(e.exception).startswith(
            'ConfigurationError("Malformed resource: '
            "bucket or collection id is invalid"
        )

    def test_resources_can_be_defined_per_bucket(self):
        raw_resources = "/buckets/stage -> /buckets/preview -> /buckets/prod"
        resources = utils.parse_resources(raw_resources)
        assert resources == {
            "/buckets/stage": {
                "source": {"bucket": "stage", "collection": None},
                "preview": {"bucket": "preview", "collection": None},
                "destination": {"bucket": "prod", "collection": None},
            }
        }

    def test_cannot_mix_per_bucket_and_per_collection(self):
        raw_resources = "/buckets/stage -> /buckets/prod/collections/boom"
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

        raw_resources = (
            "/buckets/stage/collections/boom -> "
            "/buckets/preview/collections/boom -> "
            "/buckets/prod"
        )
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

        raw_resources = (
            "/buckets/stage -> /buckets/preview/collections/boom -> /buckets/prod"
        )
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

        raw_resources = "/buckets/stage/collections/boom -> /buckets/prod"
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

    def test_cannot_repeat_source_preview_or_destination(self):
        raw_resources = "/buckets/stage -> /buckets/stage -> /buckets/prod"
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

        raw_resources = "/buckets/stage -> /buckets/preview -> /buckets/stage"
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

        raw_resources = "/buckets/stage -> /buckets/preview -> /buckets/preview"
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

    def test_cannot_repeat_resources(self):
        # Repeated source.
        raw_resources = """
        /buckets/stage -> /buckets/preview1 -> /buckets/prod1
        /buckets/stage -> /buckets/preview2 -> /buckets/prod2
        """
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

        # Repeated reviews.
        raw_resources = """
        /buckets/stage1 -> /buckets/preview -> /buckets/prod1
        /buckets/stage2 -> /buckets/preview -> /buckets/prod2
        """
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

        # Repeated destination.
        raw_resources = """
        /buckets/stage1 -> /buckets/prod
        /buckets/stage2 -> /buckets/preview -> /buckets/prod
        """
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

        # Source in other's preview.
        raw_resources = """
        /buckets/stage -> /buckets/preview -> /buckets/prod
        /buckets/bid1  -> /buckets/stage   -> /buckets/bid2
        """
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

        # Source in other's destination.
        raw_resources = """
    /buckets/b/collections/c  -> /buckets/b/collections/c2 -> /buckets/b/collections/c3
    /buckets/b/collections/ca -> /buckets/b/collections/cb -> /buckets/b/collections/c
        """
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

        # Preview in other's destination.
        raw_resources = """
    /buckets/b/collections/c0 -> /buckets/b/collections/c1 -> /buckets/b/collections/c2
    /buckets/b/collections/ca -> /buckets/b/collections/cb -> /buckets/b/collections/c1
        """
        with self.assertRaises(ConfigurationError):
            utils.parse_resources(raw_resources)

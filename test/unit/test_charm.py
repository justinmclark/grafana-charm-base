import importlib
import pathlib
import shutil
import sys
import tempfile
import textwrap
import unittest
import yaml

sys.path.append('lib')

from ops.charm import (
    CharmBase,
    RelationEvent,
)
from ops.framework import (
    Object,
)
from ops.model import (
    ActiveStatus,
    MaintenanceStatus,
    UnknownStatus,
    ModelError,
    RelationNotFoundError,
)
from ops.testing import Harness

from charm import GrafanaBase
from oci_image import OCIImageResourceError


class GrafanaBaseTest(unittest.TestCase):

    def test__grafana_source_data(self):
        # TODO: should adding and removing relation data be separate tests?
        harness = Harness(GrafanaBase, meta='''
            name: test-app
            requires:
                grafana-source:
                    interface: http
            ''')
        self.addCleanup(harness.cleanup)
        harness.begin()
        harness.set_leader(True)
        # observe events defined in the test class
        self.assertEqual(harness.charm.datastore.sources, {})

        rel_id = harness.add_relation('grafana-source', 'prometheus')
        harness.add_relation_unit(rel_id, 'prometheus/0')
        self.assertIsInstance(rel_id, int)
        rel = harness.charm.model.get_relation('grafana-source')

        # test that the unit data propagates the correct way
        # which is through the triggering of on_relation_changed
        harness.update_relation_data(rel_id,
                                     'prometheus/0',
                                     {
                                         'ingress-address': '192.0.2.1',
                                         'port': 1234,
                                     })
        print(dict(harness.charm.datastore.sources[rel_id]))
        self.assertEqual(
            {
                'host': '192.0.2.1',
                'port': 1234,
                'rel_name': 'grafana-source',
                'rel_unit': 'prometheus/0'
            },
            dict(harness.charm.datastore.sources[rel_id])
        )

        # test that setting relation data to an empty dict causes
        # the charm datastore to be cleared
        harness.update_relation_data(rel_id,
                                     'prometheus/0',
                                     {
                                         'ingress-address': None,
                                         'port': None,
                                     })
        self.assertEqual(None, harness.charm.datastore.sources.get(rel_id))

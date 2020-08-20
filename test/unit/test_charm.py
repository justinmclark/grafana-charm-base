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

    def test__http_data_source(self):
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
        self.assertEqual(
            harness.charm.grafana_source_conn,
            {'host': None, 'port': None}
        )

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
        self.assertEqual(
            {'host': '192.0.2.1', 'port': 1234},
            harness.charm.grafana_source_conn
        )

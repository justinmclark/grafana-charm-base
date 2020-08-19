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

    def test__http_interface(self):
        harness = Harness(GrafanaRelationTest, meta='''
            name: test-app
            requires:
                grafana-source:
                    interface: http
            ''')
        self.addCleanup(harness.cleanup)
        harness.begin()

        # observe events defined in the test class
        harness.charm.observe_relation_events()
        self.assertEqual(harness.charm.test_data, {})
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
            {'grafana-source-host': '192.0.2.1', 'grafana-source-port': 1234},
            self.test_data
        )


class GrafanaRelationTest(GrafanaBase):
    """This class will be used as an extension of
    `GrafanaBase` for testing purposes.
    """
    def __init__(self, framework):
        super().__init__(framework)
        self.test_data = {}  # data store for unit testing

    def observe_relation_events(self):
        # Observe events to test generic functionality
        observed_events = {
            self.grafana_source.on.server_available:
                self._on_grafana_source_available,
        }
        for event, delegator in observed_events.items():
            self.framework.observe(event, delegator)

    def _on_grafana_source_available(self, event):
        self.test_data['grafana-source-host'] = event.server_details.host
        self.test_data['grafana-source-port'] = event.server_details.port

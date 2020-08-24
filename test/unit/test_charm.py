import importlib
import pathlib
import shutil
import sys
import tempfile
import textwrap
import unittest
import yaml

from ops.testing import Harness
from ops.model import ActiveStatus, MaintenanceStatus, BlockedStatus
from charm import GrafanaK8s


class GrafanaBaseTest(unittest.TestCase):

    def test__grafana_source_data(self):
        # TODO: should adding and removing relation data be separate tests?
        harness = Harness(GrafanaK8s)
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
                'rel-name': 'grafana-source',
                'source-name': 'prometheus/0'
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

    def test__ha_database_check(self):
        """If there is a peer connection and no database (needed for HA),
        the charm should put the application in a blocked state."""

        # start charm with one peer and no database relation
        harness = Harness(GrafanaK8s)
        self.addCleanup(harness.cleanup)
        harness.begin()
        harness.set_leader(True)
        peer_rel_id = harness.add_relation('grafana', 'grafana')
        harness.add_relation_unit(peer_rel_id, 'grafana/1')
        self.assertTrue(harness.charm.has_peer)
        self.assertFalse(harness.charm.has_db)
        blocked_status = \
            BlockedStatus('Need database relation for HA Grafana.')
        self.assertEqual(harness.model.status, blocked_status)
        for event_path, observer_path, method_name in harness.framework._storage.notices(None):
            print(event_path, observer_path, method_name)

        # now add the database connection and the model should
        # have an active status
        db_rel_id = harness.add_relation('database', 'mysql')
        harness.add_relation_unit(db_rel_id, 'mysql/0')
        self.assertTrue(harness.charm.has_db)
        active_status = ActiveStatus('HA Grafana ready')
        # TODO: defer doesn't seem to work as expected here
        self.assertEqual(harness.model.status, active_status)
        for event_path, observer_path, method_name in harness.framework._storage.notices(None):
            print(event_path, observer_path, method_name)

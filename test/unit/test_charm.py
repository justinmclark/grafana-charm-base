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
                                         'host': '192.0.2.1',
                                         'port': 1234,
                                         'source-type': 'prometheus'
                                     })
        self.assertEqual(
            {
                'host': '192.0.2.1',
                'port': 1234,
                'source-name': 'prometheus/0',
                'source-type': 'prometheus',
            },
            dict(harness.charm.datastore.sources[rel_id])
        )

        # test that clearing the relation data leads to
        # the datastore for this data source being cleared
        harness.update_relation_data(rel_id,
                                     'prometheus/0',
                                     {
                                         'host': None,
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
        peer_rel = harness.charm.model.get_relation('grafana')
        harness.add_relation_unit(peer_rel_id, 'grafana/1')
        self.assertTrue(harness.charm.has_peer)
        self.assertFalse(harness.charm.has_db)
        blocked_status = \
            BlockedStatus('Need database relation for HA Grafana.')
        self.assertEqual(harness.model.status, blocked_status)

        # now add the database connection and the model should
        # not have a blocked status
        db_rel_id = harness.add_relation('database', 'mysql')
        harness.add_relation_unit(db_rel_id, 'mysql/0')

        # TODO: this is sort of a manual defer (and works) but I don't like it
        harness.charm.on.grafana_relation_joined.emit(peer_rel)
        self.assertTrue(harness.charm.has_db)
        maintenance_status = MaintenanceStatus('HA ready for configuration')
        # TODO: defer doesn't seem to work as expected here
        self.assertEqual(harness.model.status, maintenance_status)

    def test__database_relation_data(self):
        harness = Harness(GrafanaK8s)
        self.addCleanup(harness.cleanup)
        harness.begin()
        harness.set_leader(True)
        self.assertEqual(harness.charm.datastore.database, {})

        # add relation and update relation data
        rel_id = harness.add_relation('database', 'mysql')
        harness.add_relation_unit(rel_id, 'mysql/0')
        test_relation_data = {
             'type': 'mysql',
             'host': '0.1.2.3:3306',
             'name': 'my-test-db',
             'user': 'test-user',
             'password': 'super!secret!password',
        }
        harness.update_relation_data(rel_id,
                                     'mysql/0',
                                     test_relation_data)
        # check that charm datastore was properly set
        self.assertEqual(dict(harness.charm.datastore.database[rel_id]),
                         test_relation_data)

    def test__multiple_database_relation_handling(self):
        # TODO
        pass

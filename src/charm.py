#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Load modules from lib directory
import logging

import setuppath  # noqa:F401
from oci_image import OCIImageResource, OCIImageResourceError
from ops.charm import CharmBase
from ops.framework import StoredState, Object
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus, BlockedStatus

log = logging.getLogger()
# TODO: 1) if there is more than 1 grafana unit (at least one peer relation)
#           and there is no DB relation (needed for an HA cluster), put charm in blocked state
# TODO: 2) there is no use for a GrafanaBase (or any other base) at the moment - convert to K8s
#           this mainly means that we will need pod_spec_set to be triggered
# TODO: 3) create list of actions that will help users. e.g. "upload-dashboard"


class GrafanaK8s(CharmBase):
    """ The GrafanaBase class defines the common characteristics between the
        Kubernetes and traditional Grafana charms such as """

    datastore = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)

        # get container image
        self.grafana_image = OCIImageResource(self, 'grafana-image')

        # -- grafana-source relation observations
        self.framework.observe(self.on['grafana-source'].relation_changed,
                               self.on_grafana_source_changed)
        self.framework.observe(self.on['grafana-source'].relation_departed,
                               self.on_grafana_source_departed)

        # -- grafana (peer) relation observations
        self.framework.observe(self.on['grafana'].relation_joined,
                               self.on_peer_joined)

        # -- database relation observations
        self.framework.observe(self.on['database'].relation_joined,
                               self.on_database_joined)
        self.framework.observe(self.on['database'].relation_changed,
                               self.on_database_changed)

        # -- initialize states --
        self.datastore.set_default(configured=False)
        self.datastore.set_default(started=False)
        self.datastore.set_default(sources=dict())  # available data sources
        self.datastore.set_default(database=dict())  # db configuration

    @property
    def has_peer(self) -> bool:
        return len(self.model.relations['grafana']) > 0

    @property
    def has_db(self) -> bool:
        return len(self.model.relations['database']) > 0

    def on_grafana_source_changed(self, event):
        """This event handler (if the unit is the leader) will observe
        an incoming http data source and make the host/port of the
        source available in the app's datastore object (StoredState).
        """

        # if this unit is the leader, set the host/port
        # of the data source in this application's data
        if not self.unit.is_leader():
            log.debug(f"{self.unit.name} is not leader. Cannot set app data.")
            return

        # if there is no available unit, remove data-source info if it exists
        if event.unit is None:
            self._remove_source_from_datastore(event.relation.id)
            log.warning("event unit can't be None when setting data sources.")
            return

        # TODO: figure out a guarantee that this info is passed
        host = event.relation.data[event.unit].get('ingress-address')
        port = event.relation.data[event.unit].get('port')
        source_name = event.relation.data[event.unit].get('source-name')

        # check the relation data for problems
        if host is None or port is None:
            # TODO: should this be error?
            log.warning("Invalid host and/or port for grafana-source relation. "
                        "Ensure 'ingress-address' and 'port' are in app data.")
            # TODO: add test for this unit's status
            self._remove_source_from_datastore(event.relation.id)
            return

        if source_name is None:
            source_name = event.unit.name
            log.warning("No human readable name provided for 'grafana-source'"
                        "relation. Defaulting to unit name.")

        # add the new connection info to the current state
        self.datastore.sources.update({event.relation.id: {
            'host': host,
            'port': port,
            'rel-name': event.relation.name,
            'source-name': source_name,
        }})
        # TODO: test this unit's status
        self.model.unit.status = \
            MaintenanceStatus('Ready to connect to data source.')

        # TODO: real configuration -- set_pod_spec

    def on_grafana_source_departed(self, event):
        if self.unit.is_leader():
            self._remove_source_from_datastore(event.relation.id)

    def _remove_source_from_datastore(self, rel_id):
        data_source = self.datastore.sources.pop(rel_id, None)
        log.info('removing data source information from state. '
                 'host: {0}, port: {1}.'.format(
                     data_source['host'] if data_source else '',
                     data_source['port'] if data_source else '',
                 ))

    def on_peer_joined(self, event):
        """This event handler's primary goal is to ensure Grafana HA
        is possible since it needs a proper database connection.
        (e.g. MySQL or Postgresql)
        """
        if not self.unit.is_leader():
            log.debug(f'{self.unit.name} is not leader. '
                      f'Skipping on_peer_joined() handler')
            return

        # if there a new peer relation but no database relation,
        # we need to enter a blocked state
        if not self.has_db:
            log.warning('No database relation provided to Grafana cluster. '
                        'Please add database (e.g. MySQL) before proceeding.')
            self.model.status = \
                BlockedStatus('Need database relation for HA Grafana.')

            # Keep deferring this event until a database relation has joined
            # To unit test this, we may need to manually emit from the harness
            event.defer()
            return

        # let Juju operators know that HA is now possible
        self.model.status = MaintenanceStatus('HA ready for configuration')

    def on_database_joined(self, event):
        if not self.unit.is_leader():
            log.debug(f'{self.unit.name} is not leader. '
                      f'Skipping on_database_joined() handler')
            return

        # TODO: so far this is just a place holder

    def on_database_changed(self, event):
        if not self.unit.is_leader():
            log.debug(f'{self.unit.name} is not leader. '
                      f'Skipping on_database_changed() handler')
            return

        # if there is no available unit, remove data-source info if it exists
        if event.unit is None:
            log.warning("event unit can't be None when setting db config.")
            return

        # save the necessary configuration of this database connection
        # https://grafana.com/docs/grafana/latest/administration/configuration/#database


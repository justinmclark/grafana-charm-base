#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# TODO: there is no use for a GrafanaBase (or any other base) at the moment - convert to K8s
#       this mainly means that we will need pod_spec_set to be triggered
# TODO: create actions that will help users. e.g. "upload-dashboard"
# TODO: limit the number of database relations to 1 so there isn't confusion in config

import logging

import setuppath  # noqa:F401
from oci_image import OCIImageResource, OCIImageResourceError
from ops.charm import CharmBase
from ops.framework import StoredState, Object
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus, BlockedStatus

log = logging.getLogger()

# These are the relation-data fields for this Grafana charm
# In other words, when relating to this charm, these are the fields
# that will be observed by this charm.

REQUIRED_DATASOURCE_FIELDS = {
    'host',  # the hostname/IP of the data source server
    'port',  # the port of the data source server
    'source-type',  # the data source type (e.g. prometheus)
}

OPTIONAL_DATASOURCE_FIELDS = {
    'source-name',  # a human-readable name of the source
}

# https://grafana.com/docs/grafana/latest/administration/configuration/#database
REQUIRED_DATABASE_FIELDS = {
    'type',
    'host',  # int the form '<url_or_ip>:<port>', e.g. 127.0.0.1:3306
    'name',
    'user',
    'password',
}

# verify with Grafana documentation to ensure fields have valid values
# as this charm will not directly handle these cases
# TODO: fill up with optional fields - leaving blank for now
OPTIONAL_DATABASE_FIELDS = set()


class GrafanaK8s(CharmBase):
    """Charm to run Grafana data visualization on Kubernetes.

    This charm allows for high-availability (as long as a database relation
    is present).

    Developers of this charm should be aware of the Grafana provisioning docs:
    https://grafana.com/docs/grafana/latest/administration/provisioning/
    """
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
        """ Get relation data for Grafana source and set k8s pod spec.

        This event handler (if the unit is the leader) will observe
        an incoming grafana data source and make the relation data of the
        source available in the app's datastore object (StoredState).

        It verifies that the required fields have been passed and then
        sets
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

        # dictionary of all the required/optional datasource field values
        # using this as a more generic way of getting data source fields
        datasource_fields = \
            {field: event.relation.data[event.unit].get(field) for field in
             REQUIRED_DATASOURCE_FIELDS | OPTIONAL_DATASOURCE_FIELDS}

        # check the relation data for missing required fields
        if not all([datasource_fields.get(field) for field in
                    REQUIRED_DATASOURCE_FIELDS]):
            log.error(f"Missing required data fields for grafana-source "
                      f"relation: {REQUIRED_DATASOURCE_FIELDS}")
            self._remove_source_from_datastore(event.relation.id)
            return

        # specifically handle optional fields if necessary
        if datasource_fields['source-name'] is None:
            datasource_fields['source-name'] = event.unit.name
            log.warning("No human readable name provided for 'grafana-source'"
                        "relation. Defaulting to unit name.")

        # add the new datasource relation data to the current state
        self.datastore.sources.update({event.relation.id: {
            field: value for field, value in datasource_fields.items()
            if value is not None
        }})

        # TODO: test this unit's status
        self.model.unit.status = \
            MaintenanceStatus('Ready to connect to data source.')

        # TODO: real configuration -- set_pod_spec

    def on_grafana_source_departed(self, event):
        if self.unit.is_leader():
            self._remove_source_from_datastore(event.relation.id)

    def on_peer_joined(self, event):
        """Checks if HA is possible and sets model status to reflect this.

        This event handler's primary goal is to ensure Grafana HA
        is possible since it needs a proper database connection.
        (e.g. MySQL or Postgresql)
        """
        if not self.unit.is_leader():
            log.debug(f'{self.unit.name} is not leader. '
                      f'Skipping on_peer_joined() handler')
            return

        # checking self.has_peer in case this a deferred event and the
        # original peer has been departed
        if not self.has_peer:
            self.model.status = \
                MaintenanceStatus('Grafana ready for configuration')
            return

        # if there a new peer relation but no database relation,
        # we need to enter a blocked state.
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

    def on_peer_config_changed(self, event):
        """Configure update configuration if necessary."""
        # TODO

    def on_peer_config_departed(self, event):
        """A database relation is no longer required."""
        # TODO

    def on_database_joined(self, event):
        # TODO
        pass

    def on_database_changed(self, event):
        """Sets configuration information for database connection."""
        if not self.unit.is_leader():
            log.debug(f'{self.unit.name} is not leader. '
                      f'Skipping on_database_changed() handler')
            return

        if event.unit is None:
            log.warning("event unit can't be None when setting db config.")
            return

        # save the necessary configuration of this database connection
        database_fields = \
            {field: event.relation.data[event.unit].get(field) for field in
             REQUIRED_DATABASE_FIELDS | OPTIONAL_DATABASE_FIELDS}

        # if any required fields are missing, warn the user and return
        if not all([database_fields.get(field) for field in
                    REQUIRED_DATABASE_FIELDS]):
            log.error(f"Missing required data fields for related database "
                      f"relation: {REQUIRED_DATABASE_FIELDS}")
            return

        # add the new database relation data to the current state
        self.datastore.database.update({
            field: value for field, value in database_fields.items()
            if value is not None
        })

        # TODO: set pod spec

    def on_database_departed(self, event):
        # TODO
        pass

    def _remove_source_from_datastore(self, rel_id):
        # TODO: based on provisioning docs, we may want to add
        #       'deleteDatasource to Grafana configuration file
        data_source = self.datastore.sources.pop(rel_id, None)
        log.info('removing data source information from state. '
                 'host: {0}, port: {1}.'.format(
                     data_source['host'] if data_source else '',
                     data_source['port'] if data_source else '',
                 ))

    def _set_pod_spec(self):
        """Sets the Grafana pod spec with data in `self.datastore`."""
        # TODO

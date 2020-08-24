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
# TODO: 3) related to #1, we need to allow for HA -- i.e. accept peer relations


class GrafanaBase(CharmBase):
    """ The GrafanaBase class defines the common characteristics between the
        Kubernetes and traditional Grafana charms such as """

    datastore = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)

        # get container image
        self.grafana_image = OCIImageResource(self, 'grafana-image')

        # -- hook observations
        self.framework.observe(self.on['grafana-source'].relation_changed,
                               self.on_grafana_source_changed)
        self.framework.observe(self.on['grafana-source'].relation_departed,
                               self.on_grafana_source_departed)

        # -- initialize states --
        self.datastore.set_default(configured=False)
        self.datastore.set_default(started=False)
        self.datastore.set_default(sources=dict())

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
            log.warning("event.unit cannot be None when setting data sources.")
            return

        # 'ingress-address' seems to be available in k8s and non-k8s charms
        # but it also looks like 'private-address' is also available.
        # TODO: the question is, which one should I use? Check both?
        #       We might need to ensure data sources set these properly
        host = event.relation.data[event.unit].get('ingress-address')
        port = event.relation.data[event.unit].get('port')
        source_name = event.relation.data[event.unit].get('source-name')

        if source_name is None:
            source_name = event.unit.name
            log.warning("No human readable name provided for grafana-source"
                        "relation. Defaulting to unit name.")
        if host is None or port is None:
            log.debug("Invalid host and/or port for grafana-source relation.\n"
                      "Ensure 'ingress-address' and 'port' are in app data.")
            self.model.status = BlockedStatus('Invalid data source host/port')
            self._remove_source_from_datastore(event.relation.id)
        else:
            # add the new connection info to the current state
            self.datastore.sources.update({event.relation.id: {
                'host': host,
                'port': port,
                'rel-name': event.relation.name,
                'source-name': source_name,
            }})
            self.model.status = ActiveStatus('Ready to connect to data source.')

    def on_grafana_source_departed(self, event):
        # TODO: do we need to check if unit is leader here?
        if self.unit.is_leader():
            self._remove_source_from_datastore(event.relation.id)

    def _remove_source_from_datastore(self, rel_id):
        print('removing source from datastore')
        data_source = self.datastore.sources.pop(rel_id, None)
        log.info("removing data source information from state. "
                 "host: {0}, port: {1}.".format(
                     data_source['host'] if data_source else '',
                     data_source['port'] if data_source else '',
                 ))

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


class GrafanaBase(CharmBase):
    """ The GrafanaBase class defines the common characteristics between the
        Kubernetes and traditional Grafana charms such as """

    store = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)

        # get container image
        # TODO: needs confirmation that a container works well for
        #       non-k8s charms as well. If not, this should be removed
        self.grafana_image = OCIImageResource(self, 'grafana-image')

        # -- hook observations that are cloud-agnostic
        self.framework.observe(self.on['grafana-source'].relation_changed,
                               self.on_http_source_available)

        # -- initialize states --
        self.store.set_default(configured=False)
        self.store.set_default(started=False)
        self.store.set_default(sources=dict())

    def on_http_source_available(self, event):
        """This event handler (if the unit is the leader) will observe
        an incoming http data source and make the host/port of the
        source available in the app's data.

        The data sources will be stored under
        """

        # if this unit is the leader, set the host/port
        # of the data source in this application's data
        if not self.unit.is_leader():
            log.debug("{self.unit.name} is not leader. Cannot set app data.")
            return

        # if there is no available unit, remove data-source info if it exists
        if event.unit is None:
            data_source = self.store.sources.pop(event.relation.id, None)
            log.warning("removing data source information from state."
                        "host: {0}, port: {1}.".format(
                            data_source['host'],
                            data_source['port'],
                        )
            )
            log.error("event.unit cannot be None when setting data sources.")
            return

        # 'ingress-address' seems to be available in k8s and non-k8s charms
        # but it also looks like 'private-address' is also available.
        # TODO: the question is, which one should I use? Check both?
        #       We might need to ensure data sources set these properly
        #       And we might also want to ensure more data is passed
        #       as is the case in the non-k8s, reactive Grafana charm
        host = event.relation.data[event.unit].get('ingress-address')
        port = event.relation.data[event.unit].get('port')
        if host is None or port is None:
            log.debug("Invalid host and/or port for grafana-source relation.\n"
                      "Ensure 'ingress-address' and 'port' are in app data.")
            self.model.status = BlockedStatus('Invalid data source host/port')
        else:
            # add the new connection info to the current state
            self.store.sources.update({event.relation.id: {
                'host': host,
                'port': port,
                'rel_name': event.relation.name,
                'rel_unit': event.unit.name,
            }})
            self.model.status = ActiveStatus('Ready to connect to data source.')

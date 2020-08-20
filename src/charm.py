#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Load modules from lib directory
import logging

import setuppath  # noqa:F401
from oci_image import OCIImageResource, OCIImageResourceError
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus, BlockedStatus

log = logging.getLogger()


class GrafanaBase(CharmBase):
    """ The GrafanaBase class defines the common characteristics between the
        Kubernetes and traditional Grafana charms such as """

    state = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)

        # get container image
        self.grafana_image = OCIImageResource(self, 'grafana-image')

        # used to connect to a data source
        # TODO: should this be stored directly in application data? I still need to figure out how to best do this
        self.grafana_source_conn = {'host': None, 'port': None}

        # -- hook observations that are cloud-agnostic
        self.framework.observe(self.on['grafana-source'].relation_changed,
                               self.on_http_source_available)

        # -- initialize states --
        self.state.set_default(configured=False)
        self.state.set_default(started=False)

    def on_http_source_available(self, event):
        # if this unit is the leader, set the host/port
        # of the data source in this application's data
        if not self.unit.is_leader():
            log.debug("{self.unit.name} is not leader. Cannot set app data.")
            return

        # if there is no available unit, defer this event
        if event.unit is None:
            log.error("event.unit cannot be None in relation_changed handler")
            return

        # 'ingress-address' seems to be available in k8s and non-k8s charms
        # but it also looks like 'private-address' is also available.
        # TODO: the question is, which one should I use? Check both?
        host = event.relation.data[event.unit].get('ingress-address')
        port = event.relation.data[event.unit].get('port')
        if host is None or port is None:
            # if host or port are None, we still want to
            # set the grafana_source_conn to reflect this
            log.debug("Invalid host and/or port for grafana-source relation.")
            log.debug("Ensure 'ingress-address' and 'port' are in app data.")
            self.model.status = BlockedStatus('Invalid data source host/port')
        else:
            self.model.status = ActiveStatus('Ready to connect to data source.')

        # set host/port of Grafana data source in the application's data
        # TODO: linked with above todo - should this instead be application data?
        self.grafana_source_conn['host'] = host
        self.grafana_source_conn['port'] = port

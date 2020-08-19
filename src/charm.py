#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Load modules from lib directory
import logging

import setuppath  # noqa:F401
from oci_image import OCIImageResource, OCIImageResourceError
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus
import interface_http

log = logging.getLogger()


class GrafanaBase(CharmBase):
    """ The GrafanaBase class defines the common characteristics between the
        Kubernetes and traditional Grafana charms such as """

    state = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)

        # -- get container image
        self.grafana_image = OCIImageResource(self, 'grafana-image')
        self.grafana_source = interface_http.Client(self, 'grafana-source')

        # -- standard hook observation
        # TODO: find k8s/traditional agnostic things to observe

        # -- initialize states --
        self.state.set_default(configured=False)
        self.state.set_default(started=False)


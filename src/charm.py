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

log = logging.getLogger()


class GrafanaCharm(CharmBase):
    """Grafana-Kubernetes charm to work as part of LMA stack."""

    state = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)

        # -- get container image
        self.grafana_image = OCIImageResource(self, 'grafana-image')

        # -- standard hook observation
        self.framework.observe(self.on.start, self.set_pod_spec)
        self.framework.observe(self.on.config_changed, self.set_pod_spec)

        # -- initialize states --
        self.state.set_default(configured=False)
        self.state.set_default(started=False)

    def set_pod_spec(self, event):
        if not self.model.unit.is_leader():
            log.info('Unit is not leader. Skipping set_pod_spec.')
            self.model.unit.status = ActiveStatus()
            return

        log.info('Unit is leader. Setting pod spec.')
        try:
            grafana_image_details = self.grafana_image.fetch()
        except OCIImageResourceError as e:
            self.model.unit.status = e.status
            return

    def make_pod_spec(self):
        # create the juju pod spec
        pod_spec = {
            'version': 3,
            'containers': [
                {

                }
            ]
        }


if __name__ == "__main__":
    from ops.main import main
    main(GrafanaCharm)

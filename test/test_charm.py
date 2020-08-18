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

from charm import GrafanaCharm
from oci_image import OCIImageResourceError


class CharmTest(unittest.TestCase):

    def test_install(self):
        harness = Harness(GrafanaCharm, meta='''
            name: test-app
            resources:
                grafana-image:
                    type: oci-image
                    description: "Image to deploy."
            ''')
        self.addCleanup(harness.cleanup)
        harness.begin()
        harness.populate_oci_resources()
        gathered_image_details = False
        try:
            _ = harness.charm.grafana_image.fetch()
            gathered_image_details = True
        except OCIImageResourceError as e:
            pass
        self.assertTrue(gathered_image_details)

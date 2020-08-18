import sys
sys.path.append('lib')

from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)


class ServerDetails:

    def __init__(self, host=None, port=None):
        self._host = host
        self._port = port

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @classmethod
    def restore(cls, snapshot):
        if snapshot:
            return cls(host=snapshot['server_details.host'],
                       port=snapshot['server_details.port'])
        else:
            return None

    def snapshot(self):
        return {
            'server_details.host': self.host,
            'server_details.port': self.port,
        }


class ServerAvailableEvent(EventBase):

    # server_details here is explicitly provided to the `emit()` call inside
    # `Client.on_relation_changed` below. `handle` on the other hand is
    # automatically provided by `emit()`
    def __init__(self, handle, server_details):
        super().__init__(handle)
        self._server_details = server_details

    @property
    def server_details(self):
        return self._server_details

    def snapshot(self):
        return self.server_details.snapshot()

    def restore(self, snapshot):
        self._server_details = ServerDetails.restore(snapshot)


class ClientEvents(ObjectEvents):
    server_available = EventSource(ServerAvailableEvent)


class Client(Object):
    on = ClientEvents()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)
        self._relation_name = relation_name
        self.framework.observe(charm.on[relation_name].relation_changed,
                               self.on_relation_changed)

    @property
    def relation_name(self):
        return self._relation_name

    def on_relation_changed(self, event):
        # TODO: Add some logic here to pick up the right relation in case
        # the client charm is related to more than one unit. E.g. when the
        # server is in HA mode.
        relation = self.framework.model.relations[self.relation_name]
        juju_app = relation.app.name
        juju_model = self.framework.model.name

        # Fetch the k8s Service resource fronting the server pods
        service_spec = k8s.get_service_spec(juju_model=juju_model,
                                            juju_app=juju_app)

        server_details = ServerDetails(host=service_spec.host,
                                       port=service_spec.port)
        self.on.server_available.emit(server_details)

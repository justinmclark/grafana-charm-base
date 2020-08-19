import logging

from ops.framework import (
    EventBase,
    EventSource,
    Object,
    ObjectEvents,
)

log = logging.getLogger()


class ServerDetails:
    """This will be used by Grafana to connect to
    a proper data source for dashboards.
    """

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
        return cls(host=snapshot['server_details.host'],
                   port=snapshot['server_details.port'])

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
    """This class represents the client side of the Grafana
    HTTP interface. The only observed event is a relation
    changed event.
    """
    on = ClientEvents()

    def __init__(self, charm, relation_name):
        super().__init__(charm, relation_name)
        self._relation_name = relation_name

        # observe joined relations
        self.framework.observe(charm.on[relation_name].relation_changed,
                               self.on_relation_changed)

    @property
    def relation_name(self):
        return self._relation_name

    def on_relation_changed(self, event):
        # emit the server details of the http connection
        # which will give Grafana access to the data source

        # if there is no available unit, defer this event
        if event.unit is None:
            event.defer()  # TODO: verify that this is correct thing to do
            return

        # TODO: need confirmation that 'ingress address' is always available
        host = event.relation.data[event.unit].get('ingress-address')
        port = event.relation.data[event.unit].get('port')
        if host is None or port is None:
            log.debug("Invalid host/port for grafana-source relation.")
            log.debug("Ensure 'ingress-address' and 'port' are in app data.")
            event.defer()  # TODO: again, confirm that this is correct
            return

        server_details = ServerDetails(host=host, port=port)
        self.on.server_available.emit(server_details)

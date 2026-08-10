from hub.base import BaseConnector, ConnectorError, get_connector, register


def test_register_and_resolve_connector() -> None:
    @register
    class ExampleConnector(BaseConnector):
        name = "test_registry_example"
        description = "test only"

        def actions(self):
            return ["read"]

    assert isinstance(get_connector("test_registry_example"), ExampleConnector)


def test_unknown_connector_is_actionable() -> None:
    try:
        get_connector("not_registered")
    except ConnectorError as exc:
        assert "Known:" in str(exc)
    else:
        raise AssertionError("expected ConnectorError")

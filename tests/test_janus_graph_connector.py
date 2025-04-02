import janus_graph_connector


def test_import() -> None:
    """Test that the package can be imported without errors."""
    assert isinstance(janus_graph_connector.__name__, str)

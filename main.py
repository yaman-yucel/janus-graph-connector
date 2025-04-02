from pathlib import Path

from janus_graph_connector.graph_utils import JanusGraphClient

execute = True


testClient = JanusGraphClient()

test_ontology_version = "1.0"
if execute:
    node_path_dict = {
        "ontology_graph_1": {
            "nodes": "saved_dict/NODE_DICT1.json",
            "relations": "saved_dict/RELATION_DICT1.json",
        },
        "ontology_graph_2": {
            "nodes": "saved_dict/NODE_DICT2.json",
            "relations": "saved_dict/RELATION_DICT2.json",
        },
    }
    for ontology_graph_name, graph_info in node_path_dict.items():
        testClient.cleanup_graph(ontology_name=ontology_graph_name, version=test_ontology_version)

        testClient.write_nodes(
            json_file_path=Path(graph_info["nodes"]),
            ontology_name=ontology_graph_name,
            version=test_ontology_version,
        )
        testClient.write_relations(
            json_file_path=Path(graph_info["relations"]),
            ontology_name=ontology_graph_name,
            version=test_ontology_version,
        )

        NODE_DICT = testClient.read_nodes(ontology_name=ontology_graph_name, version=test_ontology_version)
        RELATION_DICT = testClient.read_relations(ontology_name=ontology_graph_name, version=test_ontology_version)

        print(NODE_DICT)
        print(RELATION_DICT)

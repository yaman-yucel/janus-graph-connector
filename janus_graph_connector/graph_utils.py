import json
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from base_ontology.node import BaseNode
from base_ontology.relation import BaseRelation
from gremlin_python.driver import serializer
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import GraphTraversalSource
from gremlin_python.process.traversal import T
from jsonschema_pydantic import jsonschema_to_pydantic


class JanusGraphClient:
    """A client for interacting with JanusGraph database."""

    def __init__(self, gremlin_url: str = "ws://localhost:8182/gremlin"):
        """
        Initialize the JanusGraph client.

        Args:
            gremlin_url: URL for the Gremlin server.
        """
        self.gremlin_url = gremlin_url
        self.serializer = serializer.GraphSONSerializersV3d0()

    @contextmanager
    def _connection(self) -> Generator[GraphTraversalSource, None, None]:
        """Context manager for handling JanusGraph connections."""
        connection = None
        try:
            connection = DriverRemoteConnection(self.gremlin_url, "g", message_serializer=self.serializer)
            g = traversal().withRemote(connection)
            yield g
        finally:
            if connection:
                connection.close()

    def write_nodes(self, json_file_path: Path | str, ontology_name: str, version: str) -> None:
        """
        Save schemas as nodes in JanusGraph with properties, including ontology name and version.

        Args:
            json_file_path: Path to JSON file containing schema definitions.
                The file should contain a dictionary where keys are node names and values are dictionaries with:
                - 'schema': JSON schema object
                - 'multiplicity': boolean flag
                - 'description': string description
            ontology_name: Name of the ontology being inserted
            version: Version identifier for the ontology
        """
        try:
            # Read the JSON file
            with open(json_file_path, encoding="utf-8") as f:
                schemas_dict = json.load(f)

            with self._connection() as g:
                for node_name, data_dict in schemas_dict.items():
                    schema = data_dict["schema"]
                    multiplicity = bool(data_dict["multiplicity"])
                    description = data_dict["description"]

                    # Convert schema to JSON string
                    schema_json = json.dumps(schema, ensure_ascii=False)

                    # Check if the node already exists
                    existing_vertex = g.V().hasLabel(node_name).has("ontology", ontology_name).has("version", version).id_().toList()

                    node_props = {
                        "schema": schema_json,
                        "multiplicity": multiplicity,
                        "description": description,
                        "ontology": ontology_name,
                        "version": version,
                    }

                    if existing_vertex:
                        # Update existing node
                        vertex = g.V(existing_vertex[0])
                        for key, value in node_props.items():
                            vertex = vertex.property(key, value)
                        vertex.iterate()
                        print(f"Updated existing node for '{node_name}' in ontology '{ontology_name}' version '{version}'")
                    else:
                        # Create new node
                        vertex = g.addV(node_name)
                        for key, value in node_props.items():
                            vertex = vertex.property(key, value)
                        vertex.iterate()
                        print(f"Created new node for '{node_name}' in ontology '{ontology_name}' version '{version}'")

                print(f"Successfully saved {len(schemas_dict)} schema nodes to JanusGraph for ontology '{ontology_name}' version '{version}'")

        except Exception as e:
            print(f"An error occurred while saving schemas: {e}")
            raise

    def write_relations(self, json_file_path: Path | str, ontology_name: str, version: str) -> None:
        """
        Create edges between nodes based on relationship definitions in a JSON file.

        Args:
            json_file_path: Path to JSON file containing relationship definitions
            ontology_name: Name of the ontology being inserted
            version: Version identifier for the ontology
        """
        try:
            # Read the JSON file
            with open(json_file_path, encoding="utf-8") as f:
                schemas_dict = json.load(f)

            with self._connection() as g:
                for edge_label, value in schemas_dict.items():
                    # Extract schema information
                    schema = value["schema"]
                    schema_json = json.dumps(schema, ensure_ascii=False)

                    # Extract node references
                    source_ref = schema["properties"]["source_node"]["$ref"]
                    target_ref = schema["properties"]["target_node"]["$ref"]

                    # Get definition names
                    source_def_name = source_ref.split("/")[-1]
                    target_def_name = target_ref.split("/")[-1]

                    # Get definitions
                    source_def = schema["$defs"][source_def_name]
                    target_def = schema["$defs"][target_def_name]

                    # Get node titles
                    source_node_title = source_def["title"]
                    target_node_title = target_def["title"]

                    # Create edge
                    g.V().hasLabel(source_node_title).has("ontology", ontology_name).has("version", version).as_("s").V().hasLabel(target_node_title).has("ontology", ontology_name).has(
                        "version", version
                    ).as_("t").addE(edge_label).from_("s").to("t").property("schema", schema_json).property("ontology", ontology_name).property("version", version).iterate()

                    print(f"Created new edge between '{source_node_title}' and '{target_node_title}' with label '{edge_label}' for ontology '{ontology_name}' version '{version}'")

        except Exception as e:
            print(f"An error occurred while saving relations: {e}")
            raise

    def read_nodes(self, ontology_name: str, version: str) -> dict[str, tuple[BaseNode, bool, str]] | None:
        """
        Retrieves nodes from JanusGraph for a specific ontology and version.

        Args:
            ontology_name: Name of the ontology to retrieve nodes from
            version: Version of the ontology to retrieve

        Returns:
            Dictionary mapping node names to a tuple containing:
              - Pydantic model derived from node's schema
              - Boolean representing multiplicity
              - String describing the node
            Returns None if an error occurs.
        """
        node_dict = {}

        try:
            with self._connection() as g:
                # Get vertices with specified ontology and version
                vertices = g.V().has("ontology", ontology_name).has("version", version).valueMap(True).toList()

                for vertex in vertices:
                    node_name = vertex[T.label]

                    # Skip if no schema
                    if "schema" not in vertex or not vertex["schema"]:
                        continue

                    try:
                        # Process schema
                        pydantic_schema_dict = json.loads(vertex["schema"][0])
                        pydantic_model = jsonschema_to_pydantic(pydantic_schema_dict)

                        # Get multiplicity
                        multiplicity = bool(vertex.get("multiplicity", [False])[0])

                        # Get description
                        description = vertex.get("description", [""])[0]

                        # Add to dictionary
                        node_dict[node_name] = (pydantic_model, multiplicity, description)

                    except Exception as schema_error:
                        print(f"Error processing schema for {node_name}: {schema_error}")
                        continue

                print(f"Successfully read {len(node_dict)} nodes from ontology '{ontology_name}' version '{version}'")
                return node_dict

        except Exception as e:
            print(f"An error occurred while reading nodes: {e}")
            return None

    def read_relations(self, ontology_name: str, version: str) -> dict[str, BaseRelation] | None:
        """
        Retrieves relations (edges) from JanusGraph for a specific ontology and version.

        Args:
            ontology_name: Name of the ontology to retrieve relations from
            version: Version of the ontology to retrieve

        Returns:
            Dictionary mapping relation names to their Pydantic models
            None if an error occurs
        """
        relation_dict = {}

        try:
            with self._connection() as g:
                # Get edges with specified ontology and version
                edges = g.E().has("ontology", ontology_name).has("version", version).elementMap().toList()

                for edge in edges:
                    edge_name = edge[T.label]

                    # Skip if no schema
                    if "schema" not in edge or not edge["schema"]:
                        continue

                    try:
                        # Process schema
                        pydantic_schema_dict = json.loads(edge["schema"])
                        pydantic_model = jsonschema_to_pydantic(pydantic_schema_dict)
                        relation_dict[edge_name] = pydantic_model

                    except Exception as schema_error:
                        print(f"Error processing schema for relation {edge_name}: {schema_error}")
                        continue

                print(f"Successfully read {len(relation_dict)} relations from ontology '{ontology_name}' version '{version}'")
                return relation_dict

        except Exception as e:
            print(f"An error occurred while reading relations: {e}")
            return None

    def cleanup_graph(self, ontology_name: str | None = None, version: str | None = None) -> None:
        """
        Clean up graph by removing vertices.

        Args:
            ontology_name: If provided, only remove vertices for this ontology
            version: If provided along with ontology_name, only remove for this specific version
        """
        try:
            with self._connection() as g:
                if ontology_name and version:
                    # Remove vertices for specific ontology and version
                    g.V().has("ontology", ontology_name).has("version", version).drop().iterate()
                    print(f"Removed all vertices for ontology '{ontology_name}' version '{version}'")

                elif ontology_name:
                    # Remove vertices for specific ontology (all versions)
                    g.V().has("ontology", ontology_name).drop().iterate()
                    print(f"Removed all vertices for ontology '{ontology_name}' (all versions)")

                else:
                    # Remove all vertices
                    g.V().drop().iterate()
                    print("Removed all vertices from the graph")

                remaining_count = g.V().count().next()
                print(f"Remaining vertex count: {remaining_count}")

        except Exception as e:
            print(f"An error occurred while cleaning up graph: {e}")
            raise

# Service Dependency Graph Manager
# Manages service topology using Neo4j for fast traversal and querying
# Save as dependency_graph.py

from neo4j import GraphDatabase
import logging
import json

logging.basicConfig(level=logging.INFO)

class DependencyGraphManager:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="password"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._init_schema()
    
    def close(self):
        self.driver.close()
    
    def _init_schema(self):
        """Initialize constraints and indexes"""
        with self.driver.session() as session:
            # Create unique constraint on service name
            try:
                session.run("CREATE CONSTRAINT service_name IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE")
            except Exception as e:
                logging.debug(f"Constraint may already exist: {e}")
    
    def add_service(self, name, metadata=None):
        """Add a service node"""
        with self.driver.session() as session:
            metadata = metadata or {}
            session.run(
                "MERGE (s:Service {name: $name}) SET s += $metadata",
                name=name, metadata=metadata
            )
            logging.info(f"Added service: {name}")
    
    def add_dependency(self, from_service, to_service, metadata=None):
        """Add a dependency edge from one service to another"""
        with self.driver.session() as session:
            metadata = metadata or {}
            session.run(
                """
                MERGE (s1:Service {name: $from_service})
                MERGE (s2:Service {name: $to_service})
                MERGE (s1)-[r:DEPENDS_ON]->(s2)
                SET r += $metadata
                """,
                from_service=from_service, to_service=to_service, metadata=metadata
            )
            logging.info(f"Added dependency: {from_service} -> {to_service}")
    
    def update_service_metadata(self, name, metadata):
        """Update service metadata (e.g., latest commit, deployment info)"""
        with self.driver.session() as session:
            session.run(
                "MATCH (s:Service {name: $name}) SET s += $metadata",
                name=name, metadata=metadata
            )
    
    def get_service(self, name):
        """Get service details"""
        with self.driver.session() as session:
            result = session.run("MATCH (s:Service {name: $name}) RETURN s", name=name)
            record = result.single()
            return dict(record["s"]) if record else None
    
    def get_dependencies(self, service_name):
        """Get all services that this service depends on"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Service {name: $name})-[r:DEPENDS_ON]->(dep:Service)
                RETURN dep.name as dependency, r
                """,
                name=service_name
            )
            return [{"service": record["dependency"], "metadata": dict(record["r"])} for record in result]
    
    def get_dependents(self, service_name):
        """Get all services that depend on this service"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Service)-[r:DEPENDS_ON]->(target:Service {name: $name})
                RETURN s.name as dependent, r
                """,
                name=service_name
            )
            return [{"service": record["dependent"], "metadata": dict(record["r"])} for record in result]
    
    def find_error_propagation_path(self, source_service, error_type=None):
        """Find all possible paths from source service through its dependents"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH path = (source:Service {name: $source})<-[:DEPENDS_ON*]-(dependent:Service)
                RETURN [node in nodes(path) | node.name] as path_nodes
                ORDER BY length(path) ASC
                LIMIT 10
                """,
                source=source_service
            )
            return [record["path_nodes"] for record in result]
    
    def annotate_error(self, service_name, error_data):
        """Annotate a service with error information"""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (s:Service {name: $name})
                SET s.last_error = $error_data,
                    s.error_timestamp = timestamp(),
                    s.error_count = coalesce(s.error_count, 0) + 1
                """,
                name=service_name, error_data=json.dumps(error_data)
            )
    
    def get_all_services(self):
        """Get all services in the graph"""
        with self.driver.session() as session:
            result = session.run("MATCH (s:Service) RETURN s.name as name, s")
            return [{"name": record["name"], "metadata": dict(record["s"])} for record in result]
    
    def clear_graph(self):
        """Clear all data (use with caution)"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            logging.warning("Cleared all graph data")


# Example usage and testing
if __name__ == "__main__":
    # Load configuration (will expand environment variables)
    try:
        from config_loader import load_config
        config_path = Path(__file__).parent / 'rca_config.yaml'
        config = load_config(str(config_path))
        neo4j_config = config['neo4j']
        graph = DependencyGraphManager(
            uri=neo4j_config['uri'],
            user=neo4j_config['user'],
            password=neo4j_config['password']
        )
    except Exception as e:
        logging.warning(f"Could not load config: {e}. Using defaults.")
        graph = DependencyGraphManager(uri="bolt://localhost:7687", user="neo4j", password="password")
    
    # Add services
    graph.add_service("frontend", {"type": "web", "language": "javascript"})
    graph.add_service("api-gateway", {"type": "api", "language": "python"})
    graph.add_service("payment-service", {"type": "microservice", "language": "java"})
    graph.add_service("db-service", {"type": "database", "language": "postgres"})
    
    # Add dependencies
    graph.add_dependency("frontend", "api-gateway")
    graph.add_dependency("api-gateway", "payment-service")
    graph.add_dependency("payment-service", "db-service")
    
    # Test queries
    print("Payment service dependencies:", graph.get_dependencies("payment-service"))
    print("Services depending on payment-service:", graph.get_dependents("payment-service"))
    print("Error propagation from db-service:", graph.find_error_propagation_path("db-service"))
    
    graph.close()

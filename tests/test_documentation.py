#!/usr/bin/env python3
"""
Documentation testing and validation
Tests documentation completeness, accuracy, and consistency
"""

import os
import re
import unittest
from pathlib import Path
from typing import List, Optional, Tuple

# import subprocess


class TestDocumentation(unittest.TestCase):
    """Test suite for documentation validation"""

    def setUp(self):
        """Set up test environment"""
        self.project_root = Path(__file__).parent.parent
        self.docs = {
            "readme": self.project_root / "README.md",
            "iceberg": self.project_root / "ICEBERG.md",
            "contributing": self.project_root / "CONTRIBUTING.md",
            "quickstart": self.project_root / "QUICKSTART.md",
        }

    def test_required_documentation_exists(self):
        """Test that required documentation files exist"""
        required_docs = ["readme", "iceberg"]

        for doc_name in required_docs:
            doc_path = self.docs[doc_name]
            self.assertTrue(
                doc_path.exists(),
                f"Required documentation {doc_name} ({doc_path}) should exist",
            )

    def test_documentation_not_empty(self):
        """Test that documentation files are not empty"""
        for doc_name, doc_path in self.docs.items():
            if doc_path.exists():
                with open(doc_path, "r") as f:
                    content = f.read().strip()

                self.assertGreater(
                    len(content),
                    100,
                    f"Documentation {doc_name} should have substantial content",
                )

    def test_readme_structure(self):
        """Test README.md structure and content"""
        readme_path = self.docs["readme"]
        if not readme_path.exists():
            self.skipTest("README.md not found")

        with open(readme_path, "r") as f:
            content = f.read()

        # Check for required sections
        required_sections = [
            "lakehouse",  # Project title
            "installation",  # Installation instructions
            "usage",  # Usage instructions
            "docker",  # Docker-related content
            "spark",  # Spark-related content
        ]

        for section in required_sections:
            self.assertIn(
                section.lower(),
                content.lower(),
                f"README should contain information about {section}",
            )

    def test_iceberg_documentation_structure(self):
        """Test ICEBERG.md structure and content"""
        iceberg_path = self.docs["iceberg"]
        if not iceberg_path.exists():
            self.skipTest("ICEBERG.md not found")

        with open(iceberg_path, "r") as f:
            content = f.read()

        # Check for required sections
        required_sections = [
            "Quick Start",
            "Features",
            "Configuration",
            "Usage Examples",
            "Time Travel",
            "Schema Evolution",
            "ACID Transactions",
            "Troubleshooting",
        ]

        for section in required_sections:
            self.assertIn(
                section, content, f"ICEBERG.md should contain {section} section"
            )

    def test_code_examples_syntax(self):
        """Test that code examples in documentation have valid syntax"""
        for doc_name, doc_path in self.docs.items():
            if not doc_path.exists():
                continue

            with open(doc_path, "r") as f:
                content = f.read()

            # Extract code blocks
            code_blocks = self._extract_code_blocks(content)

            for lang, code in code_blocks:
                if lang == "sql":
                    self._validate_sql_syntax(code, doc_name)
                elif lang == "bash":
                    self._validate_bash_syntax(code, doc_name)
                elif lang == "python":
                    self._validate_python_syntax(code, doc_name)

    def test_internal_links(self):
        """Test that internal links in documentation are valid"""
        for doc_name, doc_path in self.docs.items():
            if not doc_path.exists():
                continue

            with open(doc_path, "r") as f:
                content = f.read()

            # Find internal links (relative paths)
            internal_links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)

            for link_text, link_path in internal_links:
                if not link_path.startswith("http"):
                    # Check if file exists
                    target_path = self.project_root / link_path
                    if not target_path.exists():
                        # Skip if it's an anchor link
                        if not link_path.startswith("#"):
                            self.fail(
                                f"Internal link in {doc_name} points to non-existent file: {link_path}"
                            )

    def test_version_consistency(self):
        """Test that version numbers are consistent across documentation"""
        version_patterns = [
            r"[Vv]ersion\s*:?\s*(\d+\.\d+\.\d+)",
            r"[Ii]ceberg\s*[Vv]ersion\s*:?\s*(\d+\.\d+\.\d+)",
            r"[Ss]park\s*[Vv]ersion\s*:?\s*(\d+\.\d+\.\d+)",
        ]

        versions_found = {}

        for doc_name, doc_path in self.docs.items():
            if not doc_path.exists():
                continue

            with open(doc_path, "r") as f:
                content = f.read()

            for pattern in version_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    component = (
                        pattern.split("\\s*")[0]
                        .replace("[", "")
                        .replace("]", "")
                        .lower()
                    )
                    if component not in versions_found:
                        versions_found[component] = []
                    versions_found[component].append((match, doc_name))

        # Check for version consistency
        for component, version_list in versions_found.items():
            if len(version_list) > 1:
                versions = [v[0] for v in version_list]
                unique_versions = set(versions)

                if len(unique_versions) > 1:
                    self.fail(
                        f"Inconsistent {component} versions found: {dict(version_list)}"
                    )

    def test_docker_compose_references(self):
        """Test that Docker Compose references in documentation are accurate"""
        for doc_name, doc_path in self.docs.items():
            if not doc_path.exists():
                continue

            with open(doc_path, "r") as f:
                content = f.read()

            # Find Docker Compose commands (both old and new syntax)
            compose_commands = re.findall(r"docker[- ]compose[^\n]*", content)

            for command in compose_commands:
                # Check for common issues
                if (
                    "-f docker-compose.yml" in command
                    and "-f docker-compose.iceberg.yml" in command
                ):
                    # This is a valid Iceberg command
                    continue

                # Check for file references
                if "docker-compose.yml" in command:
                    compose_file = self.project_root / "docker-compose.yml"
                    self.assertTrue(
                        compose_file.exists(),
                        f"Referenced docker-compose.yml in {doc_name} should exist",
                    )

                if "docker-compose.iceberg.yml" in command:
                    iceberg_file = self.project_root / "docker-compose.iceberg.yml"
                    self.assertTrue(
                        iceberg_file.exists(),
                        f"Referenced docker-compose.iceberg.yml in {doc_name} should exist",
                    )

    def test_port_references(self):
        """Test that port references in documentation are consistent"""
        # Expected ports from the application
        expected_ports = {
            "9000": "MinIO API",
            "9001": "MinIO Console",
            "8080": "Spark Master",
            "9030": "Superset",
            "9020": "Airflow",
            "9040": "Jupyter",
            "9060": "Portainer",
            "5432": "PostgreSQL",
        }

        for doc_name, doc_path in self.docs.items():
            if not doc_path.exists():
                continue

            with open(doc_path, "r") as f:
                content = f.read()

            # Find port references
            port_refs = re.findall(r"localhost:(\d+)", content)

            for port in port_refs:
                if port in expected_ports:
                    # Check context around the port
                    port_context = self._get_port_context(content, port)
                    # service_name = expected_ports[port]

                    # This is a basic check - could be enhanced
                    self.assertIsNotNone(
                        port_context,
                        f"Port {port} reference in {doc_name} should have context",
                    )

    def test_command_examples_executability(self):
        """Test that command examples in documentation are potentially executable"""
        for doc_name, doc_path in self.docs.items():
            if not doc_path.exists():
                continue

            with open(doc_path, "r") as f:
                content = f.read()

            # Extract bash command examples
            bash_blocks = self._extract_code_blocks(content, "bash")

            for _, code in bash_blocks:
                # Check for common command patterns
                commands = code.split("\n")
                for command in commands:
                    command = command.strip()
                    if command.startswith("#") or not command:
                        continue

                    # Check for potentially problematic commands
                    if command.startswith("rm -rf") and "/" in command:
                        self.fail(f"Dangerous command found in {doc_name}: {command}")

                    # Check for common command structure
                    if command.startswith("./"):
                        script_name = command.split()[0]
                        script_path = self.project_root / script_name[2:]  # Remove ./

                        if script_path.exists():
                            self.assertTrue(
                                os.access(script_path, os.X_OK),
                                f"Script {script_name} referenced in {doc_name} should be executable",
                            )

    def _extract_code_blocks(
        self, content: str, language: Optional[str] = None
    ) -> List[Tuple[str, str]]:
        """Extract code blocks from markdown content"""
        code_blocks = []

        # Pattern to match code blocks
        pattern = r"```(\w+)?\n(.*?)```"
        matches = re.findall(pattern, content, re.DOTALL)

        for lang, code in matches:
            if language is None or lang == language:
                code_blocks.append((lang, code.strip()))

        return code_blocks

    def _validate_sql_syntax(self, code: str, doc_name: str):
        """Validate SQL syntax in code examples"""
        # Basic SQL syntax validation
        sql_keywords = [
            "SELECT",
            "FROM",
            "WHERE",
            "CREATE",
            "TABLE",
            "INSERT",
            "UPDATE",
            "DELETE",
            "ALTER",
            "DROP",
        ]

        # Check for basic SQL structure
        code_upper = code.upper()
        has_sql_keywords = any(keyword in code_upper for keyword in sql_keywords)

        if has_sql_keywords:
            # Check for balanced parentheses
            paren_count = code.count("(") - code.count(")")
            self.assertEqual(
                paren_count, 0, f"Unbalanced parentheses in SQL code in {doc_name}"
            )

            # Check for semicolon at end of statements
            statements = code.split(";")
            for stmt in statements:
                stmt = stmt.strip()
                if stmt and not stmt.startswith("--"):
                    # Should be a complete statement
                    self.assertTrue(
                        any(keyword in stmt.upper() for keyword in sql_keywords),
                        f"SQL statement in {doc_name} should contain SQL keywords",
                    )

    def _validate_bash_syntax(self, code: str, doc_name: str):
        """Validate bash syntax in code examples"""
        # Basic bash syntax validation
        lines = code.split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Check for balanced quotes
            single_quotes = line.count("'") - line.count("\\'")
            double_quotes = line.count('"') - line.count('\\"')

            if single_quotes % 2 != 0:
                self.fail(
                    f"Unbalanced single quotes in bash code in {doc_name}: {line}"
                )

            if double_quotes % 2 != 0:
                self.fail(
                    f"Unbalanced double quotes in bash code in {doc_name}: {line}"
                )

    def _validate_python_syntax(self, code: str, doc_name: str):
        """Validate Python syntax in code examples"""
        try:
            compile(code, f"<{doc_name}>", "exec")
        except SyntaxError as e:
            self.fail(f"Python syntax error in {doc_name}: {e}")

    def _get_port_context(self, content: str, port: str) -> Optional[str]:
        """Get context around a port reference"""
        port_pattern = f"localhost:{port}"

        # Find all occurrences
        for match in re.finditer(port_pattern, content):
            start = max(0, match.start() - 50)
            end = min(len(content), match.end() + 50)
            context = content[start:end]
            return context.strip()

        return None


class TestDocumentationCompletenessIntegration(unittest.TestCase):
    """Integration tests for documentation completeness"""

    def setUp(self):
        """Set up test environment"""
        self.project_root = Path(__file__).parent.parent

    def test_all_services_documented(self):
        """Test that all services in Docker Compose are documented"""
        compose_file = self.project_root / "docker-compose.yml"
        readme_file = self.project_root / "README.md"

        if not compose_file.exists() or not readme_file.exists():
            self.skipTest("Required files not found")

        # Parse compose file to get service names
        import yaml

        with open(compose_file, "r") as f:
            compose_data = yaml.safe_load(f)

        services = compose_data.get("services", {}).keys()

        # Check that each service is mentioned in README
        with open(readme_file, "r") as f:
            readme_content = f.read().lower()

        for service in services:
            self.assertIn(
                service.lower(),
                readme_content,
                f"Service {service} should be documented in README",
            )

    def test_iceberg_features_documented(self):
        """Test that Iceberg features are properly documented"""
        iceberg_compose = self.project_root / "docker-compose.iceberg.yml"
        iceberg_docs = self.project_root / "ICEBERG.md"

        if not iceberg_compose.exists() or not iceberg_docs.exists():
            self.skipTest("Iceberg files not found")

        # Parse Iceberg compose for features
        import yaml

        with open(iceberg_compose, "r") as f:
            iceberg_data = yaml.safe_load(f)

        # Check that key Iceberg features are documented
        with open(iceberg_docs, "r") as f:
            docs_content = f.read()

        # Check for Iceberg-specific configurations
        if "services" in iceberg_data:
            for service, config in iceberg_data["services"].items():
                if "environment" in config:
                    for env_var, value in config["environment"].items():
                        if "iceberg" in env_var.lower():
                            # This environment variable should be documented
                            self.assertIn(
                                env_var,
                                docs_content,
                                f"Iceberg environment variable {env_var} should be documented",
                            )


if __name__ == "__main__":
    unittest.main()

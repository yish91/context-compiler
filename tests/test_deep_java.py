from pathlib import Path

from context_compiler.extractors import extract_project
from context_compiler.scanner import scan_repository


def test_java_pack_adds_generic_entrypoints_and_spring_routes_without_duplicates() -> None:
    repo = (Path(__file__).parent / "fixtures" / "deep_java_repo").resolve()
    project = extract_project(scan_repository(repo))
    assert any(item.framework in ("java-generic", "java-spring") for item in project.entrypoints)
    routes = [item for item in project.endpoints if item.path == "/users" and item.method == "GET"]
    assert len(routes) == 1
    assert routes[0].framework == "java-spring"
    assert routes[0].handler == "listUsers"
    users = [item for item in project.data_models if item.name == "User"]
    assert len(users) == 1
    assert users[0].framework == "java-spring"


def test_java_pack_extracts_spring_routes_with_named_request_mapping_value(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_dir = repo / "src" / "main" / "java" / "com" / "example"
    source_dir.mkdir(parents=True)
    (source_dir / "ApiController.java").write_text(
        "package com.example;\n"
        "\n"
        "import org.springframework.web.bind.annotation.*;\n"
        "\n"
        "@RestController\n"
        '@RequestMapping(value = "/api")\n'
        "public class ApiController {\n"
        "    @GetMapping(\"/items\")\n"
        "    public String listItems() { return \"\"; }\n"
        "\n"
        "    @PostMapping\n"
        "    public String create() { return \"\"; }\n"
        "}\n",
        encoding="utf-8",
    )
    project = extract_project(scan_repository(repo))
    endpoints = sorted(project.endpoints, key=lambda e: (e.method, e.path))
    assert len(endpoints) == 2
    assert endpoints[0].method == "GET"
    assert endpoints[0].path == "/api/items"
    assert endpoints[0].handler == "listItems"
    assert endpoints[1].method == "POST"
    assert endpoints[1].path == "/api"
    assert endpoints[1].handler == "create"


def test_java_pack_extracts_spring_config_refs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_dir = repo / "src" / "main" / "java" / "com" / "example"
    source_dir.mkdir(parents=True)
    (source_dir / "Application.java").write_text(
        "package com.example;\n"
        "\n"
        "import org.springframework.beans.factory.annotation.Value;\n"
        "import org.springframework.boot.autoconfigure.SpringBootApplication;\n"
        "import org.springframework.core.env.Environment;\n"
        "\n"
        "@SpringBootApplication\n"
        "public class Application {\n"
        "    @Value(\"${APP_PORT}\")\n"
        "    private String port;\n"
        "\n"
        "    public String dbUrl(Environment env) {\n"
        "        return env.getProperty(\"DB_URL\");\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    project = extract_project(scan_repository(repo))
    config_names = {item.name for item in project.config_refs}
    assert "APP_PORT" in config_names
    assert "DB_URL" in config_names


def test_java_pack_extracts_lowercase_spring_property_keys(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_dir = repo / "src" / "main" / "java" / "com" / "example"
    source_dir.mkdir(parents=True)
    (source_dir / "Application.java").write_text(
        "package com.example;\n"
        "\n"
        "import org.springframework.beans.factory.annotation.Value;\n"
        "import org.springframework.boot.autoconfigure.SpringBootApplication;\n"
        "import org.springframework.core.env.Environment;\n"
        "\n"
        "@SpringBootApplication\n"
        "public class Application {\n"
        "    @Value(\"${server.port}\")\n"
        "    private String port;\n"
        "\n"
        "    public String dbUrl(Environment env) {\n"
        "        return env.getProperty(\"spring.datasource.url\");\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    project = extract_project(scan_repository(repo))

    config_names = {item.name for item in project.config_refs}
    assert "server.port" in config_names
    assert "spring.datasource.url" in config_names

import io
import json
import os
import sys
from typing import Any
import pytest

from aedile.shared.config import Config
from aedile.core.models import SourceFile, Symbol, Import
from aedile.core.similarity import SimilarityEngine
from aedile.core.optimizer import ReasoningOptimizer
from aedile.core.verifier import ArchitectureVerifier
from aedile.mcp.server import AedileMcpServer


def test_similarity_engine_tokenization() -> None:
    from aedile.core.similarity import tokenize
    tokens = tokenize("validateUserCredentials_API")
    assert "validate" in tokens
    assert "user" in tokens
    assert "credentials" in tokens
    assert "api" in tokens


def test_similarity_engine_indexing_and_search() -> None:
    config = Config()
    engine = SimilarityEngine(config)

    # Setup mock parsed files
    sf = SourceFile(
        filepath="/project/src/auth.py",
        relative_path="src/auth.py",
        file_hash="xyz",
        file_size=100,
        language="python",
        symbols=[
            Symbol(name="authenticate_user", kind="function", line=10, end_line=20, docstring="Validates user credentials."),
            Symbol(name="_secret_helper", kind="function", line=22, end_line=25, docstring="Internal helper", is_private=True),
        ]
    )

    engine.index_project([sf])
    
    # Assert public symbol is indexed
    assert len(engine.symbol_index) == 1
    assert engine.symbol_index[0]["name"] == "authenticate_user"

    # Test search query matching
    results = engine.search_symbols("user validation")
    assert len(results) == 1
    assert results[0]["name"] == "authenticate_user"
    assert results[0]["score"] > 0.1

    # Test stdlib matches
    stdlib = engine.check_stdlib("regular expression patterns")
    assert any(s["module"] == "re" for s in stdlib)

    # Test dependency reuse matching
    # Create temp requirements.txt
    with open("requirements.txt", "w", encoding="utf-8") as f:
        f.write("requests==2.31.0\n")
    try:
        deps = engine.check_dependencies("make http requests", ".")
        assert "requests" in deps
    finally:
        if os.path.exists("requirements.txt"):
            os.remove("requirements.txt")


def test_reasoning_optimizer() -> None:
    config = Config()
    optimizer = ReasoningOptimizer(config)

    similar = [{"name": "AuthClass", "kind": "class", "relative_path": "src/auth.py", "line": 5, "score": 0.8}]
    stdlib = [{"module": "json", "keyword": "json", "description": "built-in json parsing"}]
    deps = ["requests"]

    plan = optimizer.optimize_plan("authenticate user and download JSON payload", similar, stdlib, deps)
    
    assert "Review" in plan or "REVIEW" in plan
    assert "AuthClass" in plan
    assert "json" in plan
    assert "requests" in plan


def test_architecture_verifier() -> None:
    config = Config()
    config.layer_order = ["presentation", "domain"]
    config.layer_mappings = {
        "presentation": ["**/presentation/**"],
        "domain": ["**/domain/**"],
    }
    verifier = ArchitectureVerifier(config)

    # Domain module file
    sf_domain = SourceFile(
        filepath="/project/src/domain/entity.py",
        relative_path="src/domain/entity.py",
        file_hash="1",
        file_size=100,
        language="python",
        imports=[],
    )

    # Proposed changes: Add presentation file importing domain entity
    # (Complying with downward order)
    proposed_comply = [
        {
            "path": "src/presentation/view.py",
            "action": "add",
            "imports": ["src.domain.entity"],
        }
    ]

    violations = verifier.verify_changes("/project", [sf_domain], proposed_comply)
    assert len(violations) == 0

    # Proposed changes: Violating downward order (domain importing presentation)
    proposed_violate = [
        {
            "path": "src/domain/entity.py",
            "action": "modify",
            "imports": ["src.presentation.view"],
        }
    ]

    violations_fail = verifier.verify_changes("/project", [sf_domain], proposed_violate)
    assert len(violations_fail) >= 1
    assert violations_fail[0].rule_name == "layer_violations"


def test_path_traversal_security() -> None:
    verifier = ArchitectureVerifier(Config())
    proposed_escape = [
        {
            "path": "../../../../etc/passwd",
            "action": "add",
            "imports": [],
        }
    ]
    violations = verifier.verify_changes("/project", [], proposed_escape)
    assert len(violations) == 1
    assert violations[0].rule_name == "security_check"
    assert "Path traversal detected" in violations[0].message


def test_mcp_server_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    # Temporary patch sys.stdin and sys.stdout with new single-tool call flow
    in_buf = io.StringIO(
        json.dumps({"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1}) + "\n" +
        json.dumps({"jsonrpc": "2.0", "method": "tools/list", "id": 2}) + "\n" +
        json.dumps({
            "jsonrpc": "2.0", 
            "method": "tools/call", 
            "params": {
                "name": "aedile_consult", 
                "arguments": {
                    "proposed_plan": "parse json and make HTTP request",
                    "proposed_changes": []
                }
            }, 
            "id": 3
        }) + "\n"
    )
    out_buf = io.StringIO()

    monkeypatch.setattr(sys, "stdin", in_buf)
    monkeypatch.setattr(sys, "stdout", out_buf)

    # Setup Server and execute loop
    server = AedileMcpServer()
    server.run()

    # Retrieve stdout responses
    out_buf.seek(0)
    lines = out_buf.getvalue().strip().split("\n")
    assert len(lines) == 3

    res_init = json.loads(lines[0])
    res_tools = json.loads(lines[1])
    res_consult = json.loads(lines[2])

    assert res_init["id"] == 1
    assert res_tools["id"] == 2
    assert res_consult["id"] == 3

    # Verify tools list registers ONLY aedile_consult
    tools = res_tools["result"]["tools"]
    assert len(tools) == 1
    assert tools[0]["name"] == "aedile_consult"

    # Verify consult output matches consolidated results
    assert "content" in res_consult["result"]
    content_text = res_consult["result"]["content"][0]["text"]
    assert "Guidance" in content_text
    assert "json" in content_text

from fastapi.testclient import TestClient

from sql_agent.api import create_app
from sql_agent.jobs import SqliteJobRepository
from sql_agent.sql_config import SQLTaskRegistry
from sql_agent.security import ApiKeyAuthorizer, Principal


def test_demo_benchmark_without_local_report_opens_public_evaluation(tmp_path, monkeypatch):
    monkeypatch.setenv("SQL_AGENT_LOCAL_DEMO", "1")
    monkeypatch.setattr("sql_agent.api.LOCAL_BENCHMARK_REPORT", tmp_path / "missing.html")
    app = create_app(
        jobs=SqliteJobRepository(tmp_path / "jobs.sqlite"),
        registry=SQLTaskRegistry(), authorizer=ApiKeyAuthorizer({"test-only": Principal("test", "viewer")}),
    )
    with TestClient(app) as client:
        response = client.get("/benchmark", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"].endswith("/SQL-Agent/blob/main/docs/EVALUATION.md")


def test_local_benchmark_remains_available(tmp_path, monkeypatch):
    report = tmp_path / "benchmark.html"
    report.write_text("<h1>Recorded local evaluation</h1>")
    monkeypatch.setenv("SQL_AGENT_LOCAL_DEMO", "1")
    monkeypatch.setattr("sql_agent.api.LOCAL_BENCHMARK_REPORT", report)
    app = create_app(
        jobs=SqliteJobRepository(tmp_path / "jobs.sqlite"),
        registry=SQLTaskRegistry(), authorizer=ApiKeyAuthorizer({"test-only": Principal("test", "viewer")}),
    )
    with TestClient(app) as client:
        assert "Recorded local evaluation" in client.get("/benchmark").text

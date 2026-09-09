"""Local stdio MCP adapter for the authenticated SQL API."""
from __future__ import annotations

import json
import os
import sys
from typing import Any
import urllib.request
from urllib.parse import quote

PROTOCOL_VERSION = "2024-11-05"
TOOL_SCHEMAS = [
    {"name": "list_sql_tasks", "description": "List registered SQL tasks and fixed output contracts.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "submit_sql_task", "description": "Submit a read-only SQL task or query repair for asynchronous execution.",
     "inputSchema": {"type": "object", "properties": {
         "task_id": {"type": "string"}, "question": {"type": "string"},
         "initial_sql": {"type": "string"}, "idempotency_key": {"type": "string"}},
         "required": ["task_id", "idempotency_key"], "additionalProperties": False}},
    {"name": "get_sql_job", "description": "Read job status, output and execution evidence.",
     "inputSchema": {"type": "object", "properties": {"job_id": {"type": "string"}},
                     "required": ["job_id"], "additionalProperties": False}},
]


def api_call(path: str, payload: dict | None = None, idempotency_key: str | None = None):
    key = os.environ.get("SQL_AGENT_MCP_API_KEY")
    if not key:
        raise ValueError("SQL_AGENT_MCP_API_KEY is required")
    base = os.environ.get("SQL_AGENT_API_URL", "http://127.0.0.1:8000").rstrip("/")
    headers = {"x-api-key": key, "content-type": "application/json"}
    if idempotency_key:
        headers["idempotency-key"] = idempotency_key
    request = urllib.request.Request(base + path, headers=headers,
        data=None if payload is None else json.dumps(payload).encode())
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read())


def dispatch(message: dict) -> dict | None:
    if not isinstance(message, dict):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
    if "id" not in message:
        return None
    request_id = message["id"]
    def result(data):
        return {"jsonrpc": "2.0", "id": request_id, "result": data}
    def error(code, text):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": text}}
    method = message.get("method")
    try:
        if method == "initialize":
            return result({"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {"listChanged": False}},
                           "serverInfo": {"name": "sql-agent", "version": "0.7.0"}})
        if method == "ping":
            return result({})
        if method == "tools/list":
            return result({"tools": TOOL_SCHEMAS})
        if method != "tools/call":
            return error(-32601, "Method not found")
        params = message.get("params")
        if not isinstance(params, dict):
            return error(-32602, "Invalid params: expected an object")
        name, args = params.get("name"), params.get("arguments") or {}
        if not isinstance(args, dict):
            return error(-32602, "Invalid arguments")
        if name == "list_sql_tasks" and not args:
            output = api_call("/v1/tasks")
        elif name == "get_sql_job" and set(args) == {"job_id"} and isinstance(args["job_id"], str):
            output = api_call("/v1/jobs/" + quote(args["job_id"], safe=""))
        elif name == "submit_sql_task" and {"task_id", "idempotency_key"} <= set(args) and not set(args) - {"task_id", "idempotency_key", "question", "initial_sql"}:
            if not all(isinstance(v, str) and v for v in args.values()):
                return error(-32602, "Arguments must be nonempty strings")
            output = api_call("/v1/jobs", {k: v for k, v in args.items() if k != "idempotency_key"}, args["idempotency_key"])
        else:
            return error(-32602, "Unknown tool or invalid arguments")
        return result({"content": [{"type": "text", "text": json.dumps(output)}],
                       "structuredContent": output, "isError": False})
    except (KeyError, TypeError, ValueError, OSError) as exc:
        return result({"content": [{"type": "text", "text": str(exc)}], "isError": True})


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = dispatch(json.loads(line))
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if response is not None:
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()

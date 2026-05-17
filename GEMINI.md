# Evidentia / ScholarCounter - Project Context

## Purpose
Evidentia (ScholarCounter) is an academic paper counter-analysis agent built for the Hack-a-Claw Cloud Track. 
It analyzes academic papers, checks the quality of sources, finds counterarguments for claims, and generates a comprehensive report based on the findings.

## Codebase Structure
The repository is split into three main lanes:
- **Person A (Agents & Orchestration)**: `backend/agents/` — NemoClaw pipeline, schemas, memory handoff, manual model routing (Super vs Nano), audit logs, and sub-agents (Source Checker, Counter Researcher, Grader).
- **Person B (Backend & Tools)**: `backend/main.py`, `backend/tools/`, `backend/utils/` — Integrations and tool wrappers (Semantic Scholar, OpenAlex, Crossref).
- **Person C (Reporting & Frontend)**: `backend/report/`, `frontend/` — Report generation logic (`builder.py`) and UI presentation.

## Key Components
- **Orchestrator (`backend/agents/orchestrator.py`)**: Manages the flow by calling sub-agents and aggregating their results into an `OrchestratorOutput`. Handles model routing (reasoning vs scoring/dispatch).
- **Source Checker (`backend/agents/source_checker.py`)**: Validates citations, detects outdated sources, and flags contradiction signals using Semantic Scholar and Crossref.
- **Counter Researcher (`backend/agents/counter_researcher.py`)**: Uses NemoClaw LLMs to generate queries, retrieve opposing papers, and summarize counterarguments.
- **Grader (`backend/agents/grader.py`)**: Computes source quality scores and coverage metrics (claims backed by citations).
- **Context Store (`backend/memory/context_store.py`)**: A simple JSON-backed persistent memory store in the OpenClaw workspace directory.
- **Schemas (`backend/agents/schemas.py`)**: Defines Pydantic models for the data contracts between tools, agents, and the report builder.
- **NemoClaw Config (`nemoclaw/policy.yaml`, `sandbox-config.json`)**: Configures networking and filesystem boundaries. 

## Context & Current State
- **Person A's Plan (`JUAN-PLAN.md`)**: The orchestration core and schema definitions are mostly complete (stubbed tools integration state).
- **Data Flow**: The pipeline parses payloads, validates them via schemas, queries external tools, analyzes them with Nemotron models, stores intermediate data in the `ContextStore`, and outputs structured JSON for `builder.py` to turn into a Markdown report.
- **Models Used**: Nvidia's Nemotron models (Super for reasoning, Nano for quick scoring and formatting).

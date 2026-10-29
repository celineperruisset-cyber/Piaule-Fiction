# Piaule Fiction

> An AI-powered property management workspace that helps owners manage rental operations, applications, documents, and sensitive actions.

Piaule Fiction is an owner-first platform for orchestrating property management workflows with specialized AI agents. The owner defines the properties, rules, permissions, and communication policies. The agents structure applications, check document completeness, coordinate consent-based verification through official services such as DossierFacile, France Identité, and DGFiP tax-document verification when authorized, surface inconsistencies, prepare messages, propose viewings, and organize the next actions.

The owner remains responsible for decisions and external transmissions. Piaule Fiction is designed as software assistance and workflow orchestration, not as an undisclosed real-estate agency.

## Core workflow

```text
owner + property + rules
    -> listing and authorized channels
    -> applications linked to the right property
    -> completeness, consistency, and evidence checks
    -> explainable comparison
    -> owner or authorized partner validation
    -> viewing, lease, and permitted follow-up
```

## MVP scope

- create a workspace and a property portfolio;
- configure property rules and authorized channels;
- receive and associate applications with the correct property;
- track documents, missing items, inconsistencies, and targeted requests;
- compare applications through visible criteria and supporting evidence;
- prepare messages and viewing time slots;
- let the owner approve, reject, or revise sensitive actions;
- keep an audit trail and enforce access controls;
- retain only the information required for the selected workflow.

## Why agents instead of a single chatbot?

Piaule Fiction separates responsibilities into bounded roles such as Property and Listing, Application, Completeness, Consistency, Comparison, Viewing, and Follow-up agents. Each role has defined inputs, outputs, permissions, escalation rules, and audit events.

Agents propose and explain. Deterministic rules calculate statuses, enforce permissions, prevent duplicate actions, and block unauthorized transmissions. The owner stays in control of decisions that affect applicants, documents, messages, or external systems.

## French-market integrations as a local adapter

The current product is designed around the French rental market, so some examples refer to French services and rules:

- **DossierFacile** can provide a structured rental application and a trust signal when an authorized integration is available;
- **France Identité** represents a possible identity-verification path that requires the candidate’s consent and the appropriate official partnership;
- **DGFiP / Vérif Avis** represents an official tax-document verification path subject to authorization and consent;
- French rules for permitted rental documents, data protection, and regulated real-estate activities are documented as product constraints.

These are domain adapters, not hard-coded assumptions about the platform architecture. In another country, the same interfaces can connect to local identity, tax, document, messaging, and property-data providers. The core concepts remain the same: consent, provenance, evidence, permissions, human review, retention, and auditability.

## Product boundaries

Piaule Fiction is being built as an assistance and orchestration layer. Mandates, negotiations, lease execution, handling of funds, and regulated property-management acts must remain with the owner or an appropriately authorized partner, depending on the applicable jurisdiction and business model.

The platform does not claim that an AI system can prove a document is authentic by itself. It separates technical checks, official evidence, candidate consent, and human review. Uploaded files are intended to remain private, access-controlled, and auditable.

## Repository structure

```text
backend/            FastAPI API and owner-workspace domain contracts
frontend/           workspace prototypes and participant flows
frontend/site/      Piaule Fiction website and exported interface
fixtures/           synthetic property, application, and document fixtures
docs/               product, architecture, security, integrations, and research
sprint-dashboard/   owner-first project roadmap and delivery dashboard
infra/              deployment and operations notes
```

## Local preview

Start the project dashboard:

```bash
python3 -m http.server 8000 --directory sprint-dashboard
# open http://localhost:8000
```

Start the frontend preview:

```bash
python3 -m http.server 3000 --directory frontend
# open http://localhost:3000/owner-agent-preview.html
```

Start the local API:

```bash
python3 -m pip install -r backend/requirements.txt
PIAULE_STATE_DIRECTORY=.local-state uvicorn backend.main:app --reload --port 8000
```

The frontend can initially run with synthetic data. External credentials are configured outside Git and are not required for the local demonstration.

## Quality and security principles

- workspace isolation for each owner;
- secrets kept outside Git;
- synthetic fixtures during development;
- explicit permissions for agents and internal workers;
- human validation for sensitive external actions;
- deterministic status and retention rules;
- audit events without copying document contents;
- optional antivirus scanning for uploaded files before analysis;
- no scraping, anti-bot bypass, or third-party credentials in the product design.

## Current status

The repository contains the owner workspace model, property and application routes, document and completeness workflows, candidate access links, messaging contracts, viewing flows, agent roles, validation actions, audit events, maintenance endpoints, and synthetic tests.

The next implementation phase connects the existing API to the visual workspace and configures the real deployment environment: authentication, email delivery and reading, ClamAV on the VPS, an approved AI provider, HTTPS, monitoring, backups, and end-to-end tests.

## License and portfolio notice

This repository is shared for portfolio review and educational evaluation. See [`LICENSE`](LICENSE) for the applicable rights. It is not a production service and must not be used with real applicant documents or credentials without completing the required security, privacy, legal, and operational work.

For the French-language project notes, see [`README.fr.md`](README.fr.md).

## Documentation

- [Owner agent platform direction](docs/PRODUCT_DIRECTION_OWNER_AGENT_PLATFORM.md)
- [Workspace architecture and trust model](docs/PRODUCT_ARCHITECTURE_AND_TRUST.md)
- [Regulatory boundary](docs/REGULATORY_BOUNDARY.md)
- [Roadmap](docs/ROADMAP.md)
- [Owner product backlog](docs/PRODUCT_BACKLOG_DIFFERENTIATION.md)
- [Security and privacy](docs/SECURITY_AND_PRIVACY.md)
- [Source and connector contracts](docs/LISTING_SOURCE_CONTRACT.md)

"""Kompas Kompetencji – backend package.

Layered architecture (dependencies point inwards)::

    api  ->  services  ->  domain
     |          |             ^
     v          v             |
    container -> infrastructure adapters (repositories, AI, documents, notifications, integrations)

* ``core``          – configuration, component registry, errors, logging
* ``domain``        – pure entities & enums (no framework imports)
* ``competency``    – competency model loading, form/criteria policy
* ``scoring``       – indicator aggregation & legal outcome policies
* ``workflow``      – step-by-step paths, deadlines, step requirements
* ``assistant``     – RAG assistant (loaders, chunking, retrieval, LLM clients, guardrails)
* ``documents``     – form document builder and HTML/PDF renderers
* ``notifications`` – notifiers and reminder service
* ``integrations``  – HR (QNT) / EZD gateway abstractions and stub adapters
* ``persistence``   – generic repositories (memory / JSON file)
* ``security``      – password hashing, JWT tokens, RBAC
* ``services``      – application use-cases orchestrating the above
* ``api``           – FastAPI routers (thin HTTP layer)
"""

__version__ = "0.1.0"

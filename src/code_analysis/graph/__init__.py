"""Graph layer (planned; SPEC section 5): schema, storage adapter and queries.

Layout and dependency rule (D-0028, ``docs/architecture.md``):

* ``graph.schema`` (T004) -- immutable node/edge/evidence records, stable-ID derivation
  and the schema version.  *Records* layer: analysis stages produce these values and
  never touch storage.
* ``graph.store`` (T022) -- the explicit storage adapter (SPEC section 5.4; SQLite is
  the default candidate, no external service).  *Persistence* layer: it never imports
  ``syntax`` or any analysis package.
* ``graph.query`` (T024) -- bounded, paginated, deterministic read API over a store.
  *Queries* layer: the interfaces (``cli``, ``api``, ``viewer``) use only this public
  API.

This ``__init__`` stays empty on purpose: importing ``code_analysis.graph`` must never
pull in the query layer (the layer test forbids a lower layer importing a higher one).
"""

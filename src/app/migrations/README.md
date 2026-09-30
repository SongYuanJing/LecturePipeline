# Migration contract

No data migration in 1.9.0-candidate. Config schema remains 1 with additive application_home and task_prefix; legacy absence preserves old semantics. Any future migration must declare source/target schemas, protected data hashes, backup location, validation and rollback compatibility. Never run migrations merely by opening GUI. Preserve external user data, processed lecture identities, dictionary manual fields and provenance. Do not claim a code-only rollback can reverse an incompatible data migration.

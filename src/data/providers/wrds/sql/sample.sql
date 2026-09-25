SELECT {columns} FROM {table}
WHERE {identity_column} IN %(identities)s{date_predicate}
ORDER BY {columns}
LIMIT %(limit)s

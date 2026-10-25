"""Allowlisted error summaries; never serialize driver messages, DSNs or credentials."""
import errno
from typing import Any

SAFE_CLASSES = frozenset({
    'ValueError', 'TypeError', 'KeyError', 'FileExistsError', 'FileNotFoundError',
    'PermissionError', 'OSError', 'TimeoutError', 'ConnectionError', 'RuntimeError',
    'OperationalError', 'ProgrammingError', 'DatabaseError', 'InterfaceError',
    'UndefinedColumn', 'UndefinedTable', 'InsufficientPrivilege', 'QueryCanceled',
    'InvalidPassword', 'InvalidAuthorizationSpecification', 'ArrowInvalid', 'ArrowTypeError',
    'ImportError', 'ModuleNotFoundError', 'JSONDecodeError', 'ProviderError',
})
SQL_MESSAGES = {
    '42703': 'Source query references an undefined column.',
    '42P01': 'Source query references an undefined table.',
    '42601': 'Source query has a SQL syntax error.',
    '42501': 'Database rejected this operation for insufficient privilege.',
    '57014': 'Database canceled the query or statement timeout expired.',
    '28P01': 'Database rejected connection authentication.',
    '28000': 'Database rejected connection authorization.',
    '08001': 'Database connection could not be established.',
    '08003': 'Database connection does not exist.',
    '08006': 'Database connection failed.',
    '57P01': 'Database connection closed by administrative shutdown.',
}

SAFE_MESSAGES = frozenset({
    'Required frozen selection manifest missing: artifacts/gate_a/identity_spine/v2_selection_manifest.json; role=durable six-PERMNO selection evidence.',
    'Nonempty V2 raw directory without frozen selection manifest; preserve without overwrite.',
    'Frozen V2 protocol mismatch', 'Selection already frozen; never resample or silently overwrite',
    'Incomplete existing fixture; preserve without overwriting',
    'Existing fixture provenance mismatch', 'Existing fixture schema/count mismatch',
    'Row cap exceeded; stop without truncation/resampling',
    'No real historical identifiers; preserve frozen sample',
    'Identifier cap exceeded; preserve frozen sample',
    'Existing completion manifest differs; preserve without overwriting',
    'Frozen selection provenance mismatch', 'Frozen selection includes excluded PERMNO',
    'Frozen selection catalog evidence mismatch',
    'Explicit resume required; selection rerun is prohibited',
    'Candidate catalog must contain 6–60 unique PERMNOs',
    'Invalid/additionally excluded candidate',
    'Unsupported unconstrained PostgreSQL NUMERIC', 'Unsupported PostgreSQL source type',
    "WRDS authentication requires the user's local interactive terminal",
    'WRDS authentication requires nonempty credentials',
})


def sanitized_exception(exc: Exception) -> dict[str, Any]:
    # Revalidate nested summaries too; an upstream attribute is not a trust boundary.
    existing = getattr(exc, 'safe_diagnostic', None)
    if isinstance(existing, dict):
        allowed_messages = SAFE_MESSAGES | frozenset(SQL_MESSAGES.values()) | frozenset({
            'Exception message withheld by policy.', 'Destination already exists; overwrite refused.',
            'Required local artifact is missing.', 'Filesystem access denied.',
            'Filesystem has insufficient free space.', 'Required local Python dependency unavailable.',
            'Source value/schema conversion failed.', 'Operation timed out.',
            'Stage validation rejected input; see operation identifier.',
        })
        name = existing.get('exception_class')
        message = existing.get('sanitized_exception_message')
        result = {
            'exception_class': name if isinstance(name, str) and name in SAFE_CLASSES
            else 'OtherException',
            'sanitized_exception_message': message
            if isinstance(message, str) and message in allowed_messages
            else 'Exception message withheld by policy.',
        }
        state = existing.get('sqlstate')
        if isinstance(state, str) and state in SQL_MESSAGES:
            result['sqlstate'] = state
        stage = existing.get('provider_stage')
        if isinstance(stage, str) and stage in {'CONNECT_WRDS', 'EXECUTE_QUERY', 'VALIDATE_SCHEMA'}:
            result['provider_stage'] = stage
        return result
    original = getattr(exc, 'orig', exc)
    name = type(original).__name__
    result = {'exception_class': name if name in SAFE_CLASSES else 'OtherException',
                              'sanitized_exception_message': 'Exception message withheld by policy.'}
    state = getattr(original, 'pgcode', None)
    if isinstance(state, str) and state in SQL_MESSAGES:
        result.update(sqlstate=state, sanitized_exception_message=SQL_MESSAGES[state])
    elif isinstance(original, FileExistsError):
        result['sanitized_exception_message'] = 'Destination already exists; overwrite refused.'
    elif isinstance(original, FileNotFoundError):
        result['sanitized_exception_message'] = 'Required local artifact is missing.'
    elif isinstance(original, PermissionError):
        result['sanitized_exception_message'] = 'Filesystem access denied.'
    elif isinstance(original, OSError) and original.errno == errno.ENOSPC:
        result['sanitized_exception_message'] = 'Filesystem has insufficient free space.'
    elif isinstance(original, (ImportError, ModuleNotFoundError)):
        result['sanitized_exception_message'] = 'Required local Python dependency unavailable.'
    elif name in {'ArrowInvalid', 'ArrowTypeError', 'TypeError'}:
        result['sanitized_exception_message'] = 'Source value/schema conversion failed.'
    elif isinstance(original, TimeoutError):
        result['sanitized_exception_message'] = 'Operation timed out.'
    elif isinstance(original, ValueError):
        result['sanitized_exception_message'] = 'Stage validation rejected input; see operation identifier.'
    # Exact membership only: never redact-and-print arbitrary exception text.
    message = str(original)
    if message in SAFE_MESSAGES:
        result['sanitized_exception_message'] = message
    return result

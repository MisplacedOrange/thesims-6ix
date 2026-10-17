"""Stable rejection codes. Spellings are part of the public kernel contract."""

DUPLICATE_COMMAND = "duplicate_command"
CLOCK_REGRESSION = "clock_regression"
PHASE_REGRESSION = "phase_regression"
WRONG_PHASE = "wrong_phase"
NON_INTEGER = "non_integer"
NON_POSITIVE = "non_positive"
INVALID_ID = "invalid_id"
INVALID_KIND = "invalid_kind"
INVALID_MEMO = "invalid_memo"
INVALID_ORIGIN = "invalid_origin"
INVALID_HASH = "invalid_hash"
CREDIT_NOT_AUTHORIZED = "credit_not_authorized"
UNKNOWN_ACCOUNT = "unknown_account"
UNKNOWN_LOT = "unknown_lot"
UNKNOWN_PRODUCT = "unknown_product"
UNKNOWN_RESERVATION = "unknown_reservation"
DUPLICATE_ACCOUNT = "duplicate_account"
DUPLICATE_OWNER = "duplicate_owner"
DUPLICATE_LOT = "duplicate_lot"
SAME_ACCOUNT = "same_account"
NOT_OWNER = "not_owner"
INSUFFICIENT_CASH = "insufficient_cash"
INSUFFICIENT_STOCK = "insufficient_stock"
RESERVATION_CONFLICT = "reservation_conflict"
RESERVATION_EXCEEDED = "reservation_exceeded"
RESERVATION_EMPTY = "reservation_empty"
MASS_NOT_CONSERVED = "mass_not_conserved"
UNSAFE_LOT = "unsafe_lot"
CREDIT_NOT_RESERVABLE = "credit_not_reservable"

REJECTION_CODES = (
    DUPLICATE_COMMAND,
    CLOCK_REGRESSION,
    PHASE_REGRESSION,
    WRONG_PHASE,
    NON_INTEGER,
    NON_POSITIVE,
    INVALID_ID,
    INVALID_KIND,
    INVALID_MEMO,
    INVALID_ORIGIN,
    INVALID_HASH,
    CREDIT_NOT_AUTHORIZED,
    UNKNOWN_ACCOUNT,
    UNKNOWN_LOT,
    UNKNOWN_PRODUCT,
    UNKNOWN_RESERVATION,
    DUPLICATE_ACCOUNT,
    DUPLICATE_OWNER,
    DUPLICATE_LOT,
    SAME_ACCOUNT,
    NOT_OWNER,
    INSUFFICIENT_CASH,
    INSUFFICIENT_STOCK,
    RESERVATION_CONFLICT,
    RESERVATION_EXCEEDED,
    RESERVATION_EMPTY,
    MASS_NOT_CONSERVED,
    UNSAFE_LOT,
    CREDIT_NOT_RESERVABLE,
)

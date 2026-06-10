"""Minimal Standard 18 (BACS) file builder.

Byte positions mirror the parser in the external uk-payment-systems project
(bacs-service/pkg/standard18/parser.go). Records are fixed 80-char ASCII lines.
We emit a credit-only file: Record 1 (volume header), one or more Record 4
(direct credits), Record 5 (trailer label) and Record 9 (user trailer).
"""
from decimal import Decimal


def _field(line: list, start: int, value: str, width: int):
    """Place a left-justified, space-padded value into the fixed-width buffer."""
    text = (value or "")[:width].ljust(width)
    line[start:start + width] = list(text)


def _pence(amount) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1")))


def _blank_line() -> list:
    return list(" " * 80)


def _record1(dest_sort_code, dest_account, total_value_pence, volume, date) -> str:
    line = _blank_line()
    _field(line, 0, "1", 1)
    _field(line, 1, "0000001", 7)                       # volume number
    _field(line, 8, dest_sort_code, 9)
    _field(line, 17, dest_account, 9)
    _field(line, 55, str(total_value_pence).zfill(11), 11)
    _field(line, 66, str(volume).zfill(7), 7)
    _field(line, 73, date, 6)
    return "".join(line)


def _record4(dest_sort_code, dest_account, amount_pence, originator_name,
             reference, su_code) -> str:
    line = _blank_line()
    _field(line, 0, "4", 1)
    _field(line, 1, "0000001", 7)                       # volume header number
    _field(line, 8, dest_sort_code, 9)
    _field(line, 17, dest_account, 9)
    _field(line, 26, str(amount_pence).zfill(11), 11)
    _field(line, 37, originator_name, 15)
    _field(line, 52, reference, 14)
    _field(line, 66, su_code, 13)
    return "".join(line)


def _record5(record_count) -> str:
    line = _blank_line()
    _field(line, 0, "5", 1)
    _field(line, 1, "0000001", 7)
    _field(line, 48, str(record_count).zfill(8), 8)
    return "".join(line)


def _record9(total_value_pence, volume, hash_total) -> str:
    line = _blank_line()
    _field(line, 0, "9", 1)
    _field(line, 1, "0000001", 7)
    _field(line, 20, str(total_value_pence).zfill(11), 11)
    _field(line, 31, str(volume).zfill(9), 9)
    _field(line, 40, str(hash_total).zfill(14), 14)
    return "".join(line)


def build_credit_file(*, originator_sort_code, originator_account,
                      originator_name, su_code, date,
                      credits) -> str:
    """Build a Standard 18 direct-credit file.

    ``credits`` is a list of dicts: {dest_sort_code, dest_account, amount, reference}.
    Returns the file as a newline-joined string.
    """
    lines = []
    total_value_pence = 0
    hash_total = 0

    record4_lines = []
    for c in credits:
        pence = _pence(c["amount"])
        total_value_pence += pence
        # Hash total: sum of destination sort codes (digits only), a common
        # Standard 18 integrity check the trailer carries.
        hash_total += int("".join(ch for ch in c["dest_sort_code"] if ch.isdigit()) or 0)
        record4_lines.append(_record4(
            dest_sort_code=c["dest_sort_code"],
            dest_account=c["dest_account"],
            amount_pence=pence,
            originator_name=originator_name,
            reference=c.get("reference", ""),
            su_code=su_code,
        ))

    volume = len(credits)
    lines.append(_record1(originator_sort_code, originator_account,
                          total_value_pence, volume, date))
    lines.extend(record4_lines)
    # Record count = data records between labels (the credits themselves).
    lines.append(_record5(volume))
    lines.append(_record9(total_value_pence, volume, hash_total))
    return "\n".join(lines) + "\n"

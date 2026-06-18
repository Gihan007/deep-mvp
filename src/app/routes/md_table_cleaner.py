"""md_table_cleaner.py

Extract and clean Markdown tables from a noisy SEC 10-K Markdown dump.

Common issue in these dumps: many tables include placeholder/blank rows like:

|  |  |  |
| --- | --- | --- |
|  |  |  |

This script:
  1) finds all Markdown table blocks
  2) removes fully-empty rows
  3) drops columns that are empty across the entire table
  4) skips tables that end up empty
  5) writes all remaining tables into a new Markdown file with simple headings

Usage:
  python src/app/routes/md_table_cleaner.py \
    --input src/app/routes/AAPL_2021_10K.md \
    --output src/app/routes/AAPL_2021_10K_tables_clean.md
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_SEP_RE = re.compile(r"^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$")

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_DATE_RE = re.compile(rf"^(?:{'|'.join(_MONTHS)})\s+\d{{1,2}},\s+\d{{4}}$")
_YEAR_RE = re.compile(r"^\d{4}$")


# Defaults (edit these if you want different files by default)
DEFAULT_INPUT = Path("src/app/routes/AAPL_2021_10K.md")
DEFAULT_OUTPUT = Path("src/app/routes/AAPL_2021_10K_tables_clean.md")


def _is_empty_cell(cell: str) -> bool:
    c = cell.strip()
    if not c:
        return True
    if c.lower() in {"&nbsp;", "&#160;"}:
        return True
    # Common dash placeholders
    if c in {"—", "–", "-"}:
        return True
    return False


def _split_row(line: str) -> List[str]:
    # Remove leading/trailing pipes then split.
    raw = line.strip()
    if raw.startswith("|"):
        raw = raw[1:]
    if raw.endswith("|"):
        raw = raw[:-1]
    return [c.strip() for c in raw.split("|")]


def _escape_md_cell(cell: str) -> str:
    # Keep it simple: escape pipes, collapse newlines.
    cell = cell.replace("\n", " ").replace("\r", " ")
    cell = cell.replace("|", "\\|")
    return cell.strip()


def _looks_like_number(cell: str) -> bool:
    c = cell.strip()
    if not c:
        return False
    # allow parentheses for negatives, commas, decimals
    c = c.replace(",", "")
    # remove common currency/percent markers
    c = c.replace("$", "").replace("€", "").replace("£", "").replace("%", "")
    c = c.strip()
    if c.startswith("(") and c.endswith(")"):
        c = c[1:-1].strip()
    # em dash is non-numeric
    if c in {"—", "–", "-"}:
        return False
    # allow leading sign
    if c.startswith(("+", "-")):
        c = c[1:]
    # empty after stripping
    if not c:
        return False
    # digits or digits.decimals
    return bool(re.fullmatch(r"\d+(?:\.\d+)?", c))


def _looks_like_period(cell: str) -> bool:
    c = cell.strip()
    return bool(_DATE_RE.match(c) or _YEAR_RE.match(c))


def _normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _is_currency_token(cell: str) -> bool:
    return cell.strip() in {"$", "€", "£"}


def _is_percent_token(cell: str) -> bool:
    return cell.strip() == "%"


@dataclass
class MarkdownTable:
    header: List[str]
    rows: List[List[str]]

    def is_effectively_empty(self) -> bool:
        return all(all(_is_empty_cell(c) for c in r) for r in self.rows) and all(
            _is_empty_cell(c) for c in self.header
        )

    def cleaned(self) -> Optional["MarkdownTable"]:
        # 1) normalize width
        width = max([len(self.header)] + [len(r) for r in self.rows]) if (self.rows or self.header) else 0
        if width == 0:
            return None

        header = (self.header + [""] * width)[:width]
        rows = [((r + [""] * width)[:width]) for r in self.rows]

        # 2) drop fully-empty rows
        rows = [r for r in rows if not all(_is_empty_cell(c) for c in r)]

        # If header is empty and there are no rows, it's empty.
        if not rows and all(_is_empty_cell(c) for c in header):
            return None

        # 3) drop fully-empty columns (consider both header + all rows)
        keep_cols: List[int] = []
        for i in range(width):
            col_cells = [header[i]] + [r[i] for r in rows]
            if not all(_is_empty_cell(c) for c in col_cells):
                keep_cols.append(i)

        if not keep_cols:
            return None

        header = [header[i] for i in keep_cols]
        rows = [[r[i] for i in keep_cols] for r in rows]

        t = MarkdownTable(header=header, rows=rows)

        # 4) attempt to make it more human-friendly
        # IMPORTANT: infer headers first (period/date rows), then merge symbol columns.
        # Otherwise the inferred period labels can get stuck on the '$'/% columns.
        t = t._infer_header_and_drop_preamble()._merge_symbol_columns()

        # 5) ensure we have a header
        if all(_is_empty_cell(c) for c in t.header):
            t.header = ["Description"] + [f"Col {i}" for i in range(2, len(t.header) + 1)]
        elif t.header and _is_empty_cell(t.header[0]):
            t.header[0] = "Description"

        # 6) normalize whitespace
        t.header = [_normalize_whitespace(c) for c in t.header]
        t.rows = [[_normalize_whitespace(c) for c in r] for r in t.rows]

        return t

    def _merge_symbol_columns(self) -> "MarkdownTable":
        """Merge standalone '$' / '%' columns into adjacent value columns.

        SEC markdown dumps often split values like: | $ | 94,680 | or | 33 | % |
        We try to merge these so each period has a single value column.
        """

        header = self.header[:]
        rows = [r[:] for r in self.rows]

        def row_values(idx: int) -> List[str]:
            return [r[idx] for r in rows]

        def non_empty_ratio(idx: int) -> float:
            vals = [v.strip() for v in row_values(idx)]
            return (sum(1 for v in vals if v) / len(vals)) if vals else 0.0

        def merge_sparse_right_value_column(i: int) -> bool:
            """Handle the common SEC pattern where each period uses two columns:

            - left column contains either a currency token or the actual numeric value
            - right column contains the numeric value only when the left is a currency token

            Example rows:
              ["$", "94,680"]
              ["501", ""]

            After merge => ["$94,680"] and ["501"].
            """

            if i + 1 >= len(header):
                return False

            # Right column must be mostly empty (otherwise it's a real data column)
            if non_empty_ratio(i + 1) > 0.35:
                return False

            # Must have at least one row where left is currency and right is numeric
            has_currency_pair = any(
                _is_currency_token(r[i].strip()) and _looks_like_number(r[i + 1].strip())
                for r in rows
            )
            if not has_currency_pair:
                return False

            # If header is on the right column and left header is empty, shift it left
            if (_is_empty_cell(header[i]) or header[i].lower().startswith("col ")) and header[i + 1].strip():
                header[i] = header[i + 1]

            for r in rows:
                left = r[i].strip()
                right = r[i + 1].strip()
                if not right:
                    continue
                if _is_currency_token(left):
                    right_clean = right.lstrip("$€£").strip()
                    r[i] = f"{left}{right_clean}"
                elif not left:
                    r[i] = right
                # else: keep left as-is

            # drop right column
            del header[i + 1]
            for r in rows:
                del r[i + 1]
            return True

        def mostly_numeric(idx: int) -> bool:
            vals = [v.strip() for v in row_values(idx) if v.strip()]
            if not vals:
                return False
            return sum(1 for v in vals if _looks_like_number(v)) / len(vals) >= 0.6

        def is_sparse_currency_col(idx: int) -> bool:
            """True if this column contains only currency tokens or blanks (and at least one token)."""
            vals = [v.strip() for v in row_values(idx)]
            non_empty = [v for v in vals if v]
            if not non_empty:
                return False
            if not any(_is_currency_token(v) for v in non_empty):
                return False
            return all(_is_currency_token(v) for v in non_empty)

        def is_sparse_percent_col(idx: int) -> bool:
            """True if this column contains only '%' tokens or blanks (and at least one token)."""
            vals = [v.strip() for v in row_values(idx)]
            non_empty = [v for v in vals if v]
            if not non_empty:
                return False
            if not any(_is_percent_token(v) for v in non_empty):
                return False
            return all(_is_percent_token(v) for v in non_empty)

        i = 0
        while i < len(header):
            # 0) First merge split value columns like "$" + "94,680" where the numeric column is sparse
            if merge_sparse_right_value_column(i):
                continue

            # Merge "$" + next numeric column => "$94,680"
            if i + 1 < len(header) and is_sparse_currency_col(i) and mostly_numeric(i + 1):
                # If the period label ended up on the "$" column, move it to the numeric column
                # before dropping the "$" column.
                if _looks_like_period(header[i]) and (not _looks_like_period(header[i + 1])):
                    if _is_empty_cell(header[i + 1]) or header[i + 1].lower().startswith("col "):
                        header[i + 1] = header[i]

                for r in rows:
                    sym = r[i].strip()
                    val = r[i + 1].strip()
                    if _is_currency_token(sym) and val:
                        # Avoid double-prefixing, normalize to a single leading token
                        val = val.lstrip("$€£").strip()
                        r[i + 1] = f"{sym}{val}"
                # Drop symbol column
                del header[i]
                for r in rows:
                    del r[i]
                continue

            # Merge numeric + "%" => "33%"
            if i + 1 < len(header) and mostly_numeric(i) and is_sparse_percent_col(i + 1):
                # If the label ended up on the '%' column, move it left before dropping.
                if (not _is_empty_cell(header[i + 1])) and (
                    _is_empty_cell(header[i]) or header[i].lower().startswith("col ")
                ):
                    header[i] = header[i + 1]
                for r in rows:
                    val = r[i].strip()
                    sym = r[i + 1].strip()
                    if val and _is_percent_token(sym):
                        # Ensure exactly one trailing '%'
                        r[i] = val.rstrip("%") + "%"
                del header[i + 1]
                for r in rows:
                    del r[i + 1]
                continue

            i += 1

        return MarkdownTable(header=header, rows=rows)

    def _infer_header_and_drop_preamble(self) -> "MarkdownTable":
        """Try to infer nicer headers.

        Many tables include a preamble like:
          (blank row)
          "Years ended"
          "September 25, 2021" ...
        We look for a row containing multiple period labels and use it as header.
        """

        header = self.header[:]
        rows = [r[:] for r in self.rows]

        candidate_idx: Optional[int] = None
        for ridx in range(min(4, len(rows))):
            row = rows[ridx]
            period_cells = sum(1 for c in row if _looks_like_period(c))
            if period_cells >= 2:
                candidate_idx = ridx
                break

        if candidate_idx is not None:
            period_row = rows[candidate_idx]
            new_header: List[str] = []
            for cidx, c in enumerate(period_row):
                if cidx == 0:
                    new_header.append("Description")
                else:
                    new_header.append(c.strip() or header[cidx] or f"Col {cidx+1}")

            # Drop preamble rows up to and including candidate header row
            rows = rows[candidate_idx + 1 :]

            # Also drop a leading row like "Years ended" if it survived as first data row
            if rows and rows[0] and any("years ended" in x.lower() for x in rows[0] if x.strip()):
                rows = rows[1:]

            header = new_header

        # If first header cell empty, call it Description
        if header and _is_empty_cell(header[0]):
            header[0] = "Description"

        return MarkdownTable(header=header, rows=rows)

    def to_markdown(self) -> str:
        header = [_escape_md_cell(c) for c in self.header]
        rows = [[_escape_md_cell(c) for c in r] for r in self.rows]

        # Pad rows to header width
        width = len(header)
        rows = [((r + [""] * width)[:width]) for r in rows]

        # Choose alignment: first col left, numeric-like cols right
        right_align: List[bool] = [False] * width
        for c in range(width):
            if c == 0:
                right_align[c] = False
                continue
            col_vals = [r[c] for r in rows if r[c].strip()]
            if not col_vals:
                right_align[c] = True
                continue
            numeric_ratio = sum(1 for v in col_vals if _looks_like_number(v)) / max(1, len(col_vals))
            right_align[c] = numeric_ratio >= 0.5

        # Compute widths for pretty printing
        col_widths = [len(h) for h in header]
        for r in rows:
            for i, cell in enumerate(r):
                col_widths[i] = max(col_widths[i], len(cell))

        def pad(cell: str, idx: int) -> str:
            w = col_widths[idx]
            return cell.rjust(w) if right_align[idx] else cell.ljust(w)

        def fmt_row(r: List[str]) -> str:
            return "| " + " | ".join(pad(r[i], i) for i in range(width)) + " |"

        def fmt_sep() -> str:
            parts: List[str] = []
            for i in range(width):
                w = max(3, col_widths[i])
                if right_align[i]:
                    parts.append("-" * (w - 1) + ":")
                else:
                    parts.append(":" + "-" * (w - 1))
            return "| " + " | ".join(parts) + " |"

        out_lines = [fmt_row(header), fmt_sep()]
        out_lines.extend(fmt_row(r) for r in rows)
        return "\n".join(out_lines)



def extract_markdown_tables(lines: List[str]) -> List[Tuple[int, int, MarkdownTable]]:
    """Return (start_line_idx, end_line_idx_exclusive, table) for each table block."""
    tables: List[Tuple[int, int, MarkdownTable]] = []
    i = 0
    while i < len(lines) - 1:
        line = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else ""

        # Detect a standard markdown table header row + separator row.
        if _ROW_RE.match(line) and _SEP_RE.match(nxt):
            start = i
            block: List[str] = [line, nxt]
            i += 2
            while i < len(lines) and _ROW_RE.match(lines[i]):
                block.append(lines[i])
                i += 1

            end = i

            # Parse block into header + data rows.
            header = _split_row(block[0])
            # block[1] is separator
            data_rows = [_split_row(r) for r in block[2:]]
            tables.append((start, end, MarkdownTable(header=header, rows=data_rows)))
            continue

        i += 1

    return tables


def build_clean_tables_markdown(
    input_path: Path,
    cleaned_tables: List[MarkdownTable],
) -> str:
    title = input_path.name
    out: List[str] = [f"# Cleaned Tables from `{title}`", ""]
    for idx, t in enumerate(cleaned_tables, start=1):
        out.append(f"## Table {idx}")
        out.append("")
        out.append(t.to_markdown())
        out.append("")
    out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract + clean Markdown tables into a new .md file")
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help=f"Input markdown file path (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Output markdown file path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    # Helpful when running from other working directories
    input_path = input_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()

    text = input_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    extracted = extract_markdown_tables(lines)

    cleaned_tables: List[MarkdownTable] = []
    for _, _, t in extracted:
        ct = t.cleaned()
        if ct is None:
            continue
        if ct.is_effectively_empty():
            continue
        cleaned_tables.append(ct)

    output_md = build_clean_tables_markdown(input_path=input_path, cleaned_tables=cleaned_tables)
    output_path.write_text(output_md, encoding="utf-8")

    print(f"Input:   {input_path}")
    print(f"Found:   {len(extracted)} table blocks")
    print(f"Wrote:   {output_path}")
    print(f"Kept:    {len(cleaned_tables)} cleaned tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

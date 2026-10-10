"""07 §8.4 (parse half): the register is read exactly as uploaded. The Sheet 1 write-back half lands with DA-4."""
import io
from datetime import datetime

from openpyxl import Workbook

from app.register import map_columns, parse_verbatim

FIG1 = ["Bill no.", "Date", "Job No.", "Customer", "Ledger Account", "State Code", "GST No.", "Total Cost",
        "Discount", "Packing", "Freight", "Insurance", "IGST", "CGST", "SGST", "TCSCollection", "Round",
        "Gross Amt.", "Tax", "BU", "E Invoice"]
LAKH = "#,##,##0.00"


def _fig1_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.append(["Konkan Marine Controls Ltd"])               # title rows above the header, as exports have
    ws.append(["Sales Register 01-04-2025 to 31-03-2026"])
    ws.append(FIG1)
    ws.append(["G2/0001/25", datetime(2025, 4, 3), "J-11", "Arabian Shipyards Pvt Ltd", "SALES ACCOUNT", 27,
               "27AAPFU0939F1ZV", 1559322.0, 0, 0, 0, 0, 0, 140339.0, 140339.0, 0, 0, 1840000.0,
               "CGST/SGST 9%", "Valves", "Complete"])
    ws.append(["CN/0008/25", datetime(2025, 9, 30), None, "Arabian Shipyards Pvt Ltd", "SALES RETURN", 0,
               None, -250000, 0, 0, 0, 0, 0, 0, 0, 0, 0, -250000, None, "Valves", "Incomplete"])
    ws.append(["G2/0002/25", datetime(2025, 4, 4), "J-12", None, None, None, None, 15559.3249])
    for row in ws.iter_rows(min_row=4, max_row=6):
        row[1].number_format = "DD-MM-YYYY"
        for c in row[7:18]:
            c.number_format = LAKH
    inj = ws.cell(row=6, column=4)
    inj.value = '=HYPERLINK("http://x","ok")'
    inj.data_type = "s"                                     # the client sent text that looks like a formula
    ws.cell(row=6, column=5, value="#N/A").data_type = "s"  # '#N/A' typed as text
    ws.cell(row=6, column=6, value="#N/A")                    # a genuine error cell
    ws.cell(row=6, column=18, value="=H6*1.18")              # a real formula: cached value + formula text
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_fig1_headers_all_map():
    m = map_columns(FIG1)
    assert len(m) == 21
    assert m["doc_no"] == "Bill no." and m["gstin"] == "GST No." and m["taxable"] == "Total Cost"
    assert m["gross"] == "Gross Amt." and m["einvoice"] == "E Invoice" and m["tcs"] == "TCSCollection"
    assert map_columns(["Customers", "Remarks"]) == {}       # unknown headers are never guessed


def test_xlsx_verbatim_values_formats_order():
    headers, rows = parse_verbatim(_fig1_xlsx(), "register.xlsx")
    assert headers == FIG1                                   # header row found under the title rows
    assert [r["row_no"] for r in rows] == [1, 2, 3]
    inv, cn, odd = (r["cells"] for r in rows)
    assert inv[0] == {"v": "G2/0001/25", "t": "s"}
    assert inv[1] == {"v": "2025-04-03T00:00:00", "t": "d", "fmt": "DD-MM-YYYY"}
    assert inv[5] == {"v": 27, "t": "n"}
    assert inv[7] == {"v": 1559322.0, "t": "n", "fmt": LAKH}
    assert cn[0]["v"] == "CN/0008/25" and cn[7]["v"] == -250000 and cn[5]["v"] == 0   # CN stays a negative row
    assert cn[6] == {"v": None, "t": ""}                    # blank GSTIN stays blank
    assert odd[7]["v"] == 15559.3249                         # sub-paise value kept verbatim (only mapping rounds)
    assert odd[3] == {"v": '=HYPERLINK("http://x","ok")', "t": "s"}   # text, not a live formula
    assert odd[4] == {"v": "#N/A", "t": "s"} and odd[5] == {"v": "#N/A", "t": "e"}
    assert odd[17]["f"] == "=H6*1.18"                        # formula listed; cached value as stored
    assert all(len(r["cells"]) == 21 for r in rows)


def test_csv_every_cell_stays_text():
    text = ('Bill no.,Date,Customer,GST No.,Total Cost\r\n'
            'G2/0012/25,03-04-2025,"Mandovi Fisheries, Goa",030AAKCK4821M1Z5,0012\r\n'
            'G2/0013/25,04-04-2025,"=HYPERLINK(""http://x"",""ok"")",,"1,18,000.50"\r\n')
    headers, rows = parse_verbatim(text.encode("utf-8-sig"), "reg.csv")
    assert headers == ["Bill no.", "Date", "Customer", "GST No.", "Total Cost"]
    a, b = (r["cells"] for r in rows)
    assert a[4] == {"v": "0012", "t": "s", "fmt": "@"}      # leading zeros survive
    assert a[3]["v"] == "030AAKCK4821M1Z5" and a[2]["v"] == "Mandovi Fisheries, Goa"
    assert b[2]["v"] == '=HYPERLINK("http://x","ok")' and b[2]["t"] == "s"
    assert b[4]["v"] == "1,18,000.50" and b[3]["v"] == ""


def test_semicolon_csv_and_cp1252():
    text = "Bill no.;Date;Customer;Total Cost\nG11/0001/25;01.04.2025;Caf\xe9 Marine;500\n"
    headers, rows = parse_verbatim(text.encode("cp1252"), "reg.csv")
    assert headers[0] == "Bill no." and rows[0]["cells"][2]["v"] == "Caf\xe9 Marine"


def test_unsupported_format_is_actionable():
    try:
        parse_verbatim(b"\xd0\xcf\x11\xe0legacy", "register.xls")
    except ValueError as e:
        assert str(e).startswith("INVALID_ARGUMENT") and ".xlsx" in str(e)
    else:
        raise AssertionError("expected ValueError")

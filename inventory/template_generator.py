from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter


HEADERS = [
    ('Product Name *', 30),
    ('Category', 20),
    ('Quantity', 12),
    ('Unit Price *', 14),
    ('Cost Price', 14),
    ('Unit Label', 14),
    ('Supplier', 22),
    ('Paid (YES/NO)', 14),
    ('Preorder (YES/NO)', 18),
    ('Reorder Level', 14),
]


def generate_product_template(store):
    wb = Workbook()

    # ── Products sheet ───────────────────────────────────────────────────
    ws = wb.active
    ws.title = 'Products'

    header_fill = PatternFill('solid', fgColor='D8F3DC')
    header_font = Font(bold=True)

    for col, (header, width) in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
        ws.column_dimensions[get_column_letter(col)].width = width

    ws.freeze_panes = 'A2'

    # YES/NO validation for Paid (col 8) and Preorder (col 9)
    yn_dv = DataValidation(type='list', formula1='"YES,NO"', allow_blank=True)
    yn_dv.sqref = 'H2:I1048576'
    ws.add_data_validation(yn_dv)

    # Default values in sample row
    ws.cell(row=2, column=3, value=0)
    ws.cell(row=2, column=6, value='unit')
    ws.cell(row=2, column=8, value='YES')
    ws.cell(row=2, column=9, value='NO')
    ws.cell(row=2, column=10, value=5)

    # Instruction comment on A1
    comment = Comment(
        'Fill in your products below.\nProduct Name and Unit Price are required.\nSKU will be auto-generated.',
        'SalesApp'
    )
    ws['A1'].comment = comment

    # ── Categories reference sheet ───────────────────────────────────────
    ws2 = wb.create_sheet('Categories')
    ws2.cell(row=1, column=1, value='Category Name').font = header_font
    ws2.column_dimensions['A'].width = 28

    categories = store.categories.all().order_by('name')
    for i, cat in enumerate(categories, start=2):
        ws2.cell(row=i, column=1, value=cat.name)

    ws2.sheet_state = 'visible'

    return wb

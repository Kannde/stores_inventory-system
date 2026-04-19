import calendar
from datetime import date, timedelta


PERIOD_CHOICES = [
    ('today',         'Today'),
    ('yesterday',     'Yesterday'),
    ('this_week',     'This Week'),
    ('last_week',     'Last Week'),
    ('this_month',    'This Month'),
    ('last_month',    'Last Month'),
    ('this_quarter',  'This Quarter'),
    ('last_quarter',  'Last Quarter'),
    ('this_year',     'This Year'),
    ('last_year',     'Last Year'),
]


def _quarter_bounds(d):
    q = (d.month - 1) // 3
    sm = q * 3 + 1
    em = sm + 2
    start = date(d.year, sm, 1)
    end = date(d.year, em, calendar.monthrange(d.year, em)[1])
    return start, end, q + 1


def resolve_period(request, today, default='this_week'):
    period = request.GET.get('period', default)
    date_from_raw = request.GET.get('date_from', '')
    date_to_raw = request.GET.get('date_to', '')

    if period == 'today':
        start = end = today
        label = f"Today · {today.strftime('%d %b %Y')}"

    elif period == 'yesterday':
        d = today - timedelta(days=1)
        start = end = d
        label = f"Yesterday · {d.strftime('%d %b %Y')}"

    elif period == 'this_week':
        start = today - timedelta(days=today.weekday())
        end = today
        label = f"This Week · {start.strftime('%d')}–{end.strftime('%d %b %Y')}"

    elif period == 'last_week':
        end = today - timedelta(days=today.weekday() + 1)
        start = end - timedelta(days=6)
        label = f"Last Week · {start.strftime('%d')}–{end.strftime('%d %b %Y')}"

    elif period == 'this_month':
        start = date(today.year, today.month, 1)
        end = today
        label = today.strftime('%B %Y')

    elif period == 'last_month':
        first_this = date(today.year, today.month, 1)
        end = first_this - timedelta(days=1)
        start = date(end.year, end.month, 1)
        label = end.strftime('%B %Y')

    elif period == 'this_quarter':
        start, end_q, q = _quarter_bounds(today)
        end = today
        label = f"Q{q} {today.year} · {start.strftime('%b')}–{end_q.strftime('%b %Y')}"

    elif period == 'last_quarter':
        first_this_q, _, _ = _quarter_bounds(today)
        d = first_this_q - timedelta(days=1)
        start, end, q = _quarter_bounds(d)
        label = f"Q{q} {d.year} · {start.strftime('%b')}–{end.strftime('%b %Y')}"

    elif period == 'this_year':
        start = date(today.year, 1, 1)
        end = today
        label = str(today.year)

    elif period == 'last_year':
        y = today.year - 1
        start = date(y, 1, 1)
        end = date(y, 12, 31)
        label = str(y)

    else:
        period = 'custom'
        try:
            start = date.fromisoformat(date_from_raw)
        except (ValueError, TypeError):
            start = today - timedelta(days=30)
        try:
            end = date.fromisoformat(date_to_raw)
        except (ValueError, TypeError):
            end = today
        if start > end:
            start, end = end, start
        if start == end:
            label = start.strftime('%d %b %Y')
        elif start.year == end.year:
            label = f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}"
        else:
            label = f"{start.strftime('%d %b %Y')} – {end.strftime('%d %b %Y')}"

    return {
        'period': period,
        'start_date': start,
        'end_date': end,
        'period_label': label,
        'f_date_from': start.isoformat(),
        'f_date_to': end.isoformat(),
        'period_choices': PERIOD_CHOICES,
    }


def parse_entity_filters(request):
    return {
        'active_staff_id': request.GET.get('staff_id', ''),
        'active_category_id': request.GET.get('category_id', ''),
        'active_product_id': request.GET.get('product_id', ''),
    }

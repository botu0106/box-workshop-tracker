"""Small SVG charts drawn on the server.

No JavaScript chart library is needed, so the page keeps its strict Content Security
Policy. Each point carries a <title>, which the browser shows as a tooltip.
"""
import math
from datetime import timedelta

import pandas as pd
from markupsafe import Markup, escape

WIDTH, HEIGHT = 560, 230
LEFT, RIGHT, TOP, BOTTOM = 40, 10, 26, 30
FONT = 14
BLUE = "#257de0"
ORANGE = "#f47230"
GRID = "#e5e5e5"
AXIS_TEXT = "#6c757d"


def _scale(value, low, high, out_low, out_high):
    if high == low:
        return (out_low + out_high) / 2
    return out_low + (value - low) * (out_high - out_low) / (high - low)


def _nice_max(value):
    """Round the top of the y axis up to 1, 2, 4, 5 or 8 times a power of ten."""
    if value <= 0:
        return 1
    magnitude = 10 ** math.floor(math.log10(value))
    for factor in (1, 2, 4, 5, 8, 10):
        if value <= factor * magnitude:
            return factor * magnitude
    return 10 * magnitude


def _frame(y_max, y_unit, days, start, whole=False):
    """Grid lines, y labels and date labels shared by all charts."""
    parts = []
    ticks = 4
    if whole and y_max < ticks:
        ticks = int(y_max)  # counts: never show "1.5 orders"
    for i in range(ticks + 1):
        value = y_max * i / ticks
        y = _scale(value, 0, y_max, HEIGHT - BOTTOM, TOP)
        parts.append(f'<line x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        label = f"{value:g}"
        parts.append(f'<text x="{LEFT - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="{FONT}" '
                     f'fill="{AXIS_TEXT}">{escape(label)}</text>')
    parts.append(f'<text x="4" y="{FONT}" font-size="{FONT}" fill="{AXIS_TEXT}">{escape(y_unit)}</text>')
    step = max(1, days // 4)
    for d in range(0, days + 1, step):
        x = _scale(d, 0, days, LEFT, WIDTH - RIGHT)
        label = (start + timedelta(days=d)).strftime("%d.%m")
        parts.append(f'<text x="{x:.1f}" y="{HEIGHT - 8}" text-anchor="middle" font-size="{FONT}" '
                     f'fill="{AXIS_TEXT}">{label}</text>')
    return parts


def _svg(parts, label):
    body = "".join(parts)
    return Markup(
        f'<svg viewBox="0 0 {WIDTH} {HEIGHT}" width="100%" role="img" aria-label="{escape(label)}" '
        f'style="font-family: inherit; max-width: 720px; display: block; margin: 0 auto">{body}</svg>'
    )


def daily_counts_chart(orders, now, days=30):
    """Orders received and completed per day, as two lines."""
    start = (now - timedelta(days=days)).date()
    index = pd.date_range(start, now.date(), freq="D")
    received = orders["received_at"].dt.normalize().value_counts().reindex(index, fill_value=0)
    done = orders.loc[orders["completed"], "completed_at"].dt.normalize()
    completed = done.value_counts().reindex(index, fill_value=0)
    if received.sum() == 0 and completed.sum() == 0:
        return None

    y_max = _nice_max(max(received.max(), completed.max()))
    parts = _frame(y_max, "buyurtma", days, start, whole=True)
    slot = (WIDTH - RIGHT - LEFT) / (days + 1)
    bar = max(slot / 2 - 1, 1)
    for i, (day, got, done_count) in enumerate(zip(index, received, completed)):
        x = LEFT + i * slot
        for offset, value, color, name in ((0, got, BLUE, "qabul qilindi"),
                                           (bar, done_count, ORANGE, "tayyor boʻldi")):
            if value:
                top = _scale(value, 0, y_max, HEIGHT - BOTTOM, TOP)
                parts.append(f'<rect x="{x + offset:.1f}" y="{top:.1f}" width="{bar:.1f}" '
                             f'height="{HEIGHT - BOTTOM - top:.1f}" rx="1.5" fill="{color}">'
                             f'<title>{day:%d.%m}: {value} ta {name}</title></rect>')
    return _svg(parts, "Kunlik qabul qilingan va tayyor boʻlgan buyurtmalar")


def order_trend_chart(orders, now, value_column, unit, label, multiplier=1, days=30):
    """One dot per completed order (by completion date) with a rolling median line."""
    start = (now - timedelta(days=days)).date()
    data = orders[orders["completed"]].dropna(subset=[value_column])
    data = data[data["completed_at"].dt.date >= start].sort_values("completed_at")
    if data.empty:
        return None

    values = data[value_column] * multiplier
    y_max = _nice_max(float(values.max()))
    parts = _frame(y_max, unit, days, start)

    def x_of(ts):
        return _scale((ts - pd.Timestamp(start)).total_seconds() / 86400, 0, days, LEFT, WIDTH - RIGHT)

    rolling = values.rolling(5, min_periods=1).median()
    if len(data) >= 3:
        path = " ".join(
            f"{x_of(ts):.1f},{_scale(v, 0, y_max, HEIGHT - BOTTOM, TOP):.1f}"
            for ts, v in zip(data["completed_at"], rolling)
        )
        parts.append(f'<polyline points="{path}" fill="none" stroke="{ORANGE}" stroke-width="2"/>')
    for ts, v, code in zip(data["completed_at"], values, data["order_code"]):
        x, y = x_of(ts), _scale(v, 0, y_max, HEIGHT - BOTTOM, TOP)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{BLUE}" stroke="#fff" stroke-width="2">'
                     f'<title>№ {escape(code)}, {ts:%d.%m}: {v:.1f} {escape(unit)}</title></circle>')
    return _svg(parts, label)


def weekly_boxes_chart(weekly):
    """Good boxes produced per week (Monday to Sunday), one column per week."""
    if weekly.empty or weekly["good"].sum() == 0:
        return None
    y_max = _nice_max(float(weekly["good"].max()))
    parts = []
    for i in range(5):
        value = y_max * i / 4
        y = _scale(value, 0, y_max, HEIGHT - BOTTOM, TOP)
        parts.append(f'<line x1="{LEFT + 12}" x2="{WIDTH - RIGHT}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
        parts.append(f'<text x="{LEFT + 6}" y="{y + 4:.1f}" text-anchor="end" font-size="{FONT}" '
                     f'fill="{AXIS_TEXT}">{value:,.0f}</text>'.replace(",", " "))
    parts.append(f'<text x="4" y="{FONT}" font-size="{FONT}" fill="{AXIS_TEXT}">dona</text>')
    slot = (WIDTH - RIGHT - LEFT - 12) / len(weekly)
    bar = slot * 0.6
    for i, row in enumerate(weekly.itertuples()):
        x = LEFT + 12 + i * slot + (slot - bar) / 2
        end = row.week + timedelta(days=6)
        if row.good:
            top = _scale(row.good, 0, y_max, HEIGHT - BOTTOM, TOP)
            parts.append(f'<rect x="{x:.1f}" y="{top:.1f}" width="{bar:.1f}" '
                         f'height="{HEIGHT - BOTTOM - top:.1f}" rx="3" fill="{BLUE}">'
                         f'<title>{row.week:%d.%m}–{end:%d.%m}: {row.good:,} ta sifatli quti, '
                         f'{row.orders} ta buyurtma, brak {row.defective:,}</title></rect>'.replace(",", " "))
        if i % 2 == len(weekly) % 2 or len(weekly) <= 6:
            parts.append(f'<text x="{x + bar / 2:.1f}" y="{HEIGHT - 8}" text-anchor="middle" '
                         f'font-size="{FONT}" fill="{AXIS_TEXT}">{row.week:%d.%m}</text>')
    return _svg(parts, "Haftalik ishlab chiqarilgan sifatli qutilar")


def make_all(orders, now):
    return {
        "daily": daily_counts_chart(orders, now),
        "lead": order_trend_chart(orders, now, "lead_days", "kun",
                                  "Har bir tayyor buyurtmaning muddati"),
        "defects": order_trend_chart(orders, now, "defect_rate", "%",
                                     "Har bir tayyor buyurtmadagi brak", multiplier=100),
    }

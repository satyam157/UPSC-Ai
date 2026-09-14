"""
codeforces_visualizer.py
========================
UPSC-AI Codeforces-Style Performance Visualizer
- Codeforces Rating Graph replaced with Marks Graph (horizontal tier bands, trajectory line, latest-test red ring)
- Codeforces Calendar Activity Heatmap (52 weeks, Mon/Wed/Fri labels, month headers, year selector)
- Brightness/Red color logic: less activity = muted dark red, more activity = bright glowing red
- Separate visual themes, tiers, cutoff benchmarks, and heatmaps for Prelims vs Mains
- Codeforces 3-column statistics cards (all time, last year, last month problems and consecutive day streaks)
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, date, timedelta, timezone
import plotly.graph_objects as go

# IST = UTC+5:30. Always use this for 'today' so date comparisons
# match the user's local calendar, not the UTC server clock.
_IST = timezone(timedelta(hours=5, minutes=30))

def _today_ist() -> date:
    """Returns today's date in Indian Standard Time (IST = UTC+5:30)."""
    return datetime.now(_IST).date()


# ─── TIER DEFINITIONS ────────────────────────────────────────────────────────

PRELIMS_TIERS = [
    {"name": "Aspirant (Beginner)", "min": 0, "max": 60, "color": "#94a3b8", "fill": "rgba(148, 163, 184, 0.22)"},
    {"name": "Pupil (Developing)", "min": 60, "max": 80, "color": "#4ade80", "fill": "rgba(74, 222, 128, 0.22)"},
    {"name": "Specialist (Cutoff Zone)", "min": 80, "max": 100, "color": "#38bdf8", "fill": "rgba(56, 189, 248, 0.22)"},
    {"name": "Expert (Selection Zone)", "min": 100, "max": 120, "color": "#818cf8", "fill": "rgba(129, 140, 248, 0.22)"},
    {"name": "Master (Top 1%)", "min": 120, "max": 140, "color": "#c084fc", "fill": "rgba(192, 132, 252, 0.22)"},
    {"name": "Grandmaster (AIR Top)", "min": 140, "max": 200, "color": "#f87171", "fill": "rgba(248, 113, 113, 0.22)"},
]

MAINS_TIERS = [
    {"name": "Developing", "min": 0, "max": 70, "color": "#94a3b8", "fill": "rgba(148, 163, 184, 0.22)"},
    {"name": "Average", "min": 70, "max": 85, "color": "#4ade80", "fill": "rgba(74, 222, 128, 0.22)"},
    {"name": "Good (Interview Zone)", "min": 85, "max": 100, "color": "#38bdf8", "fill": "rgba(56, 189, 248, 0.22)"},
    {"name": "High Scorer", "min": 100, "max": 115, "color": "#818cf8", "fill": "rgba(129, 140, 248, 0.22)"},
    {"name": "Exceptional", "min": 115, "max": 130, "color": "#c084fc", "fill": "rgba(192, 132, 252, 0.22)"},
    {"name": "All India Ranker", "min": 130, "max": 250, "color": "#f87171", "fill": "rgba(248, 113, 113, 0.22)"},
]


def get_tier_info(marks, exam_type="Prelims"):
    tiers = PRELIMS_TIERS if exam_type.lower() == "prelims" else MAINS_TIERS
    for t in tiers:
        if t["min"] <= marks < t["max"]:
            return t
    return tiers[-1] if marks >= tiers[-1]["min"] else tiers[0]


# ─── CODEFORCES MARKS RATING GRAPH ──────────────────────────────────────────

def build_codeforces_graph_fig(records, exam_type="Prelims", scale_mode="Standard"):
    """
    Builds a Codeforces-style Marks graph:
    - Horizontal rank tier bands in background
    - Test dates on X-axis (formatted like Codeforces: 'May 2024', 'Jul 2024'...)
    - Marks on Y-axis (replacing rating)
    - Golden connected line with dot markers
    - Current/latest test point highlighted with a prominent red ring
    - Benchmark reference line (e.g. Cutoff 92 marks for Prelims, 100 marks for Mains)
    """
    is_prelims = (exam_type.lower() == "prelims")
    tiers = PRELIMS_TIERS if is_prelims else MAINS_TIERS
    max_y = 200 if is_prelims else 250
    line_color = "#eab308" if is_prelims else "#06b6d4"  # Amber for Prelims, Cyan/Teal for Mains
    marker_color = "#fef08a" if is_prelims else "#a5f3fc"
    
    fig = go.Figure()
    
    # 1. Background Horizontal Rank Tier Bands (Exact Codeforces Style)
    shapes = []
    for t in tiers:
        shapes.append(dict(
            type="rect",
            xref="paper",
            yref="y",
            x0=0,
            x1=1,
            y0=t["min"],
            y1=t["max"],
            fillcolor=t["fill"],
            line=dict(width=0.5, color="rgba(255, 255, 255, 0.08)"),
            layer="below"
        ))
        
    # 2. Benchmark Reference Line
    benchmark_val = 92.0 if is_prelims else 100.0
    benchmark_label = "Cutoff Target (~92)" if is_prelims else "Selection Benchmark (100+)"
    shapes.append(dict(
        type="line",
        xref="paper",
        yref="y",
        x0=0,
        x1=1,
        y0=benchmark_val,
        y1=benchmark_val,
        line=dict(color="#f43f5e", width=1.8, dash="dashdot"),
        layer="above"
    ))

    if not records:
        fig.update_layout(
            shapes=shapes,
            xaxis=dict(
                showgrid=True,
                gridcolor="rgba(255, 255, 255, 0.08)",
                title=dict(text="Test Date", font=dict(color="#94a3b8", size=13))
            ),
            yaxis=dict(
                range=[0, max_y],
                showgrid=True,
                gridcolor="rgba(255, 255, 255, 0.08)",
                title=dict(text=f"Marks ({'Prelims / 200' if is_prelims else 'Mains / 250'})", font=dict(color="#94a3b8", size=13))
            ),
            plot_bgcolor="#161b22",
            paper_bgcolor="#161b22",
            margin=dict(l=50, r=30, t=40, b=40),
            annotations=[dict(
                text="No test records yet. Attempt a test or click 'Load Demo Codeforces Data' below!",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(color="#94a3b8", size=14)
            )]
        )
        return fig

    # Sort records chronologically
    sorted_records = sorted(records, key=lambda r: r["date"])
    
    dates = []
    marks = []
    customdata = []
    
    for r in sorted_records:
        d_str = r["date"].strftime("%Y-%m-%d") if isinstance(r["date"], (date, datetime)) else str(r["date"])
        m_val = float(r["marks"])
        
        # Scale handling: if user chose raw vs standardized
        if scale_mode == "Standardized (200/250)" and r.get("total_marks") and r["total_marks"] > 0:
            std_max = 200.0 if is_prelims else 250.0
            if r["total_marks"] != std_max and r["total_marks"] <= 50:
                m_val = round((m_val / float(r["total_marks"])) * std_max, 2)
                
        dates.append(d_str)
        marks.append(m_val)
        tier_inf = get_tier_info(m_val, exam_type)
        customdata.append([
            r.get("name", "Test"),
            r.get("total_marks", max_y),
            r.get("accuracy", 0.0),
            tier_inf["name"],
            r.get("correct", 0),
            r.get("wrong", 0),
            r.get("source", "Test")
        ])

    # 3. Trajectory Line + Markers
    fig.add_trace(go.Scatter(
        x=dates,
        y=marks,
        mode="lines+markers",
        name="Marks Trajectory",
        line=dict(color=line_color, width=3, shape="spline", smoothing=0.3),
        marker=dict(
            size=8,
            color=marker_color,
            line=dict(color="#b45309" if is_prelims else "#0891b2", width=1.8)
        ),
        customdata=customdata,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "📅 Date: <b>%{x}</b><br>"
            "🎯 Marks: <b>%{y:.1f}</b> / %{customdata[1]}<br>"
            "📈 Accuracy: <b>%{customdata[2]:.1f}%</b><br>"
            "🏷️ Tier: <span style='color:#38bdf8'>%{customdata[3]}</span><br>"
            "✅ Correct: %{customdata[4]} | ❌ Wrong: %{customdata[5]}<br>"
            "<i>%{customdata[6]}</i>"
            "<extra></extra>"
        )
    ))

    # 4. Highlight the Latest/Most Recent Test with Codeforces Signature Red Ring!
    if len(dates) > 0:
        latest_x = [dates[-1]]
        latest_y = [marks[-1]]
        latest_custom = [customdata[-1]]
        
        # Outer red glow ring
        fig.add_trace(go.Scatter(
            x=latest_x,
            y=latest_y,
            mode="markers",
            name="Current Score",
            marker=dict(
                size=16,
                color="rgba(239, 68, 68, 0.25)",
                line=dict(color="#ef4444", width=2.5)
            ),
            hoverinfo="skip",
            showlegend=False
        ))
        
        # Inner white dot
        fig.add_trace(go.Scatter(
            x=latest_x,
            y=latest_y,
            mode="markers",
            name="Latest Point",
            marker=dict(size=7, color="#ffffff"),
            hoverinfo="skip",
            showlegend=False
        ))

    # Benchmark annotation
    annotations = [
        dict(
            x=1,
            y=benchmark_val,
            xref="paper",
            yref="y",
            text=f"🚩 {benchmark_label}",
            showarrow=False,
            font=dict(color="#f43f5e", size=11, family="Inter, sans-serif"),
            xanchor="right",
            yanchor="bottom",
            bgcolor="rgba(22, 27, 34, 0.8)",
            bordercolor="rgba(244, 63, 94, 0.4)",
            borderwidth=1,
            borderpad=3
        )
    ]

    # Calculate reasonable Y axis range
    actual_max = max(marks) if marks else max_y
    y_upper = max(max_y, int(actual_max + 15))

    fig.update_layout(
        shapes=shapes,
        annotations=annotations,
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.08)",
            tickformat="%b %Y",
            dtick="M2",
            linecolor="rgba(255, 255, 255, 0.15)",
            tickfont=dict(color="#94a3b8", size=11)
        ),
        yaxis=dict(
            range=[0, y_upper],
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.08)",
            linecolor="rgba(255, 255, 255, 0.15)",
            tickfont=dict(color="#94a3b8", size=11),
            title=dict(text="Marks", font=dict(color="#cbd5e1", size=13, weight="bold"))
        ),
        plot_bgcolor="#161b22",
        paper_bgcolor="#161b22",
        margin=dict(l=55, r=35, t=30, b=40),
        height=380,
        showlegend=False,
        hoverlabel=dict(
            bgcolor="#1e293b",
            bordercolor="#475569",
            font=dict(color="#f8fafc", family="Inter, sans-serif", size=12)
        )
    )
    
    return fig


# ─── CODEFORCES ACTIVITY HEATMAP (BRIGHTNESS / RED LOGIC) ────────────────────

def calculate_codeforces_stats(records, target_year=None):
    """
    Computes Codeforces statistics:
    - All-time problems/tests solved & max streak
    - Last year problems/tests solved & last year streak
    - Last month problems/tests solved & last month streak
    """
    if not records:
        return {
            "all_solved": 0, "all_streak": 0,
            "year_solved": 0, "year_streak": 0,
            "month_solved": 0, "month_streak": 0,
            "day_counts": {}, "day_test_counts": {}
        }

    today = _today_ist()
    one_year_ago = today - timedelta(days=365)
    one_month_ago = today - timedelta(days=30)

    # Map date -> total questions solved (or 1 test if total_questions=0)
    day_counts = {}
    day_test_counts = {}
    for r in records:
        d = r["date"]
        if isinstance(d, datetime):
            d = d.date()
        elif isinstance(d, str):
            try:
                d = datetime.strptime(d[:10], "%Y-%m-%d").date()
            except Exception:
                continue

        q_count = r.get("total_questions") or r.get("attempted") or 1
        day_counts[d] = day_counts.get(d, 0) + q_count
        day_test_counts[d] = day_test_counts.get(d, 0) + 1

    # Totals
    all_solved = sum(day_counts.values())
    year_solved = sum(cnt for d, cnt in day_counts.items() if d >= one_year_ago)
    month_solved = sum(cnt for d, cnt in day_counts.items() if d >= one_month_ago)

    # Streaks calculation helper
    def get_max_streak_in_range(start_d, end_d):
        cur_d = start_d
        max_s = 0
        curr_s = 0
        while cur_d <= end_d:
            if cur_d in day_counts:
                curr_s += 1
                if curr_s > max_s:
                    max_s = curr_s
            else:
                curr_s = 0
            cur_d += timedelta(days=1)
        return max_s

    min_date = min(day_counts.keys()) if day_counts else today
    all_streak = get_max_streak_in_range(min_date, today)
    year_streak = get_max_streak_in_range(one_year_ago, today)
    month_streak = get_max_streak_in_range(one_month_ago, today)

    return {
        "all_solved": all_solved,
        "all_streak": all_streak,
        "year_solved": year_solved,
        "year_streak": year_streak,
        "month_solved": month_solved,
        "month_streak": month_streak,
        "day_counts": day_counts,
        "day_test_counts": day_test_counts
    }


def get_heatmap_cell_color(count, exam_type="Prelims"):
    """
    User color logic:
    'more color look like less bright green where as less color look like more bright.
     so use less color as red and more color as bright red. use this logic'
    
    Empty (0): subtle dark slate
    Low (1): Dark / muted red (less bright)
    Moderate (2): Medium deep red
    High (3): Vibrant strong red
    Top (4+): Glowing, ultra-bright neon red (more bright!)
    """
    is_prelims = (exam_type.lower() == "prelims")
    
    if count == 0:
        return "#1e2430", "#1e2430"  # bg, border
    
    if is_prelims:
        # RED SPECTRUM (Less = Dark/Muted Red, More = Bright/Glowing Red)
        if count == 1:
            return "#6b1414", "#851e1e"   # Level 1: Muted dark burgundy
        elif count == 2:
            return "#a81d1d", "#c52828"   # Level 2: Medium crimson
        elif count == 3:
            return "#e11d48", "#f43f5e"   # Level 3: Strong vibrant red
        else:
            return "#ff0033", "#ff4d6d"   # Level 4: Ultra-bright glowing neon red!
    else:
        # MAINS: Distinct Purple/Violet Spectrum (Less = Dark/Muted Violet, More = Neon Violet/Pink)
        if count == 1:
            return "#3b0764", "#581c87"   # Level 1: Deep dark purple
        elif count == 2:
            return "#7e22ce", "#9333ea"   # Level 2: Medium purple
        elif count == 3:
            return "#a855f7", "#c084fc"   # Level 3: Bright violet
        else:
            return "#f0abfc", "#e879f9"   # Level 4: Glowing electric neon pink/purple!


def render_codeforces_heatmap_html(records, exam_type="Prelims", selected_year="All Time"):
    """
    Renders the exact Codeforces activity heatmap:
    - 52-week calendar grid (7 rows: Sun to Sat, labeled Mon, Wed, Fri)
    - Month headers across the top
    - Codeforces 3-column stats block beneath
    - Red brightness logic requested by user
    """
    stats = calculate_codeforces_stats(records)
    day_counts = stats["day_counts"]
    day_test_counts = stats["day_test_counts"]

    today = _today_ist()
    
    # Determine start and end date for 52 weeks
    if selected_year and selected_year != "All Time":
        try:
            yr = int(selected_year)
            start_date = date(yr, 1, 1)
            end_date = date(yr, 12, 31)
        except Exception:
            end_date = today
            start_date = today - timedelta(days=364)
    else:
        end_date = today
        start_date = today - timedelta(days=364)

    # Align start_date to Sunday
    start_offset = (start_date.weekday() + 1) % 7
    calendar_start = start_date - timedelta(days=start_offset)
    
    # Generate weeks
    cur = calendar_start
    weeks = []
    month_positions = []
    current_month = None
    week_idx = 0
    
    while cur <= end_date:
        week = []
        for row in range(7):
            day_obj = cur
            cnt = day_counts.get(day_obj, 0)
            tests_cnt = day_test_counts.get(day_obj, 0)
            
            # Record month header at start of new month (usually row 0 or 1)
            if row == 0 and day_obj.month != current_month and day_obj <= end_date:
                current_month = day_obj.month
                month_name = day_obj.strftime("%b")
                month_positions.append((week_idx, month_name))
                
            week.append({
                "date": day_obj,
                "date_str": day_obj.strftime("%b %d, %Y"),
                "count": cnt,
                "tests_cnt": tests_cnt,
                "in_range": (start_date <= day_obj <= end_date)
            })
            cur += timedelta(days=1)
            
        weeks.append(week)
        week_idx += 1
        if cur > end_date and cur.weekday() == 6:
            break

    # Build Month Labels HTML
    month_headers_html = '<div style="display:flex;margin-left:36px;margin-bottom:6px;height:18px;font-size:11px;color:#94a3b8;font-family:Inter,sans-serif;">'
    total_cols = len(weeks)
    prev_col = -1
    for col_idx, m_name in month_positions:
        left_margin = (col_idx - prev_col - 1) * 15 if prev_col >= 0 else col_idx * 15
        month_headers_html += f'<span style="margin-left:{max(0, left_margin)}px;display:inline-block;width:28px;">{m_name}</span>'
        prev_col = col_idx + 1
    month_headers_html += '</div>'

    # Build Grid HTML
    day_labels = ["", "Mon", "", "Wed", "", "Fri", ""]
    grid_rows_html = ""
    for r in range(7):
        label = day_labels[r]
        row_html = f'<div style="display:flex;align-items:center;margin-bottom:3px;">'
        row_html += f'<div style="width:34px;font-size:10px;color:#64748b;font-family:Inter,sans-serif;text-align:right;padding-right:6px;line-height:13px;">{label}</div>'
        
        for w_idx, week in enumerate(weeks):
            cell = week[r]
            c_date = cell["date_str"]
            cnt = cell["count"]
            t_cnt = cell["tests_cnt"]
            in_range = cell["in_range"]
            
            if not in_range:
                bg_color = "transparent"
                border_color = "transparent"
                tooltip = ""
            else:
                bg_color, border_color = get_heatmap_cell_color(t_cnt, exam_type)
                tooltip = f"{t_cnt} test{'s' if t_cnt != 1 else ''} ({cnt} problems) on {c_date}" if t_cnt > 0 else f"No tests on {c_date}"
            
            row_html += (
                f'<div title="{tooltip}" style="'
                f'width:12px;height:12px;margin-right:3px;border-radius:2px;'
                f'background-color:{bg_color};border:1px solid {border_color};'
                f'cursor:pointer;transition:transform 0.1s ease;'
                f'" onmouseover="this.style.transform=\'scale(1.25)\'" onmouseout="this.style.transform=\'scale(1)\'">'
                f'</div>'
            )
        row_html += '</div>'
        grid_rows_html += row_html

    # Legend HTML (Less = Dark/Muted Red -> More = Bright Glowing Red)
    is_prelims = (exam_type.lower() == "prelims")
    theme_title = "Prelims Tests Activity" if is_prelims else "Mains Answer Writing Activity"
    c0, b0 = get_heatmap_cell_color(0, exam_type)
    c1, b1 = get_heatmap_cell_color(1, exam_type)
    c2, b2 = get_heatmap_cell_color(2, exam_type)
    c3, b3 = get_heatmap_cell_color(3, exam_type)
    c4, b4 = get_heatmap_cell_color(4, exam_type)
    
    legend_html = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;padding:0 8px;font-size:11px;color:#94a3b8;font-family:Inter,sans-serif;">
      <span>Activity scale: Less (Darker) ➔ More (Bright Glowing)</span>
      <div style="display:flex;align-items:center;gap:4px;">
        <span>Less</span>
        <div style="width:11px;height:11px;background:{c0};border:1px solid {b0};border-radius:2px;"></div>
        <div style="width:11px;height:11px;background:{c1};border:1px solid {b1};border-radius:2px;"></div>
        <div style="width:11px;height:11px;background:{c2};border:1px solid {b2};border-radius:2px;"></div>
        <div style="width:11px;height:11px;background:{c3};border:1px solid {b3};border-radius:2px;"></div>
        <div style="width:11px;height:11px;background:{c4};border:1px solid {b4};border-radius:2px;box-shadow:0 0 5px {c4};"></div>
        <span>More</span>
      </div>
    </div>
    """

    # 3-Column Codeforces Stats HTML
    stats_html = f"""
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;margin-top:22px;padding-top:18px;border-top:1px solid rgba(255,255,255,0.08);font-family:Inter,sans-serif;">
      <!-- Column 1: All time -->
      <div>
        <div style="font-size:26px;font-weight:800;color:#f8fafc;line-height:1.2;">
          {stats['all_solved']} problems
        </div>
        <div style="font-size:12px;color:#94a3b8;margin-bottom:14px;">
          solved for all time
        </div>
        <div style="font-size:26px;font-weight:800;color:#f8fafc;line-height:1.2;">
          {stats['all_streak']} days
        </div>
        <div style="font-size:12px;color:#94a3b8;">
          in a row max.
        </div>
      </div>
      
      <!-- Column 2: Last year -->
      <div>
        <div style="font-size:26px;font-weight:800;color:#f8fafc;line-height:1.2;">
          {stats['year_solved']} problems
        </div>
        <div style="font-size:12px;color:#94a3b8;margin-bottom:14px;">
          solved for the last year
        </div>
        <div style="font-size:26px;font-weight:800;color:#f8fafc;line-height:1.2;">
          {stats['year_streak']} days
        </div>
        <div style="font-size:12px;color:#94a3b8;">
          in a row for the last year
        </div>
      </div>
      
      <!-- Column 3: Last month -->
      <div>
        <div style="font-size:26px;font-weight:800;color:#f8fafc;line-height:1.2;">
          {stats['month_solved']} problems
        </div>
        <div style="font-size:12px;color:#94a3b8;margin-bottom:14px;">
          solved for the last month
        </div>
        <div style="font-size:26px;font-weight:800;color:#f8fafc;line-height:1.2;">
          {stats['month_streak']} days
        </div>
        <div style="font-size:12px;color:#94a3b8;">
          in a row for the last month
        </div>
      </div>
    </div>
    """

    # Assemble complete container
    card_html = f"""
    <div style="background:#161b22;border:1px solid rgba(255,255,255,0.12);border-radius:12px;padding:20px;margin-top:16px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
        <div style="color:#cbd5e1;font-size:13px;font-weight:600;font-family:Inter,sans-serif;">
          📌 {theme_title}
        </div>
        <div style="color:#94a3b8;font-size:12px;font-family:Inter,sans-serif;">
          Year: <b style="color:#f8fafc;">{selected_year}</b>
        </div>
      </div>
      
      <div style="overflow-x:auto;padding-bottom:6px;">
        {month_headers_html}
        {grid_rows_html}
      </div>
      
      {legend_html}
      {stats_html}
    </div>
    """
    return card_html


# ─── CODEFORCES RATING CARD ──────────────────────────────────────────────────

def render_rating_card_html(records, exam_type="Prelims", scale_mode="Standard"):
    """
    Renders a Codeforces-style rating badge showing:
    - Current Rating: today's test marks (or 'No test today' if none)
    - Highest Rating: best marks ever achieved with tier name and color
    Both displayed as marks/denomination (e.g., 128/200 or 105/250).
    """
    if not records:
        return ""

    is_prelims = (exam_type.lower() == "prelims")
    max_possible = 200 if is_prelims else 250
    exam_label = "Prelims" if is_prelims else "Mains"
    today = _today_ist()

    # Sort chronologically
    sorted_records = sorted(records, key=lambda r: r["date"])

    # Compute marks values (respect scale_mode)
    def scaled_marks(r):
        m_val = float(r["marks"])
        if scale_mode == "Standardized (200/250)" and r.get("total_marks") and r["total_marks"] > 0:
            std_max = 200.0 if is_prelims else 250.0
            if r["total_marks"] != std_max and r["total_marks"] <= 50:
                m_val = round((m_val / float(r["total_marks"])) * std_max, 2)
        return m_val

    all_marks = [scaled_marks(r) for r in sorted_records]

    # ── Highest Rating (all time) ──
    highest_marks = max(all_marks)
    highest_tier  = get_tier_info(highest_marks, exam_type)
    highest_idx   = all_marks.index(highest_marks)
    highest_date  = sorted_records[highest_idx]["date"]
    highest_date_str = highest_date.strftime("%d %b %Y") if hasattr(highest_date, "strftime") else str(highest_date)[:10]

    # ── Current Rating: today's test only ──
    def record_date(r):
        d = r["date"]
        if isinstance(d, datetime):
            return d.date()
        return d

    today_records = [r for r in sorted_records if record_date(r) == today]
    has_today = len(today_records) > 0

    if has_today:
        # Use the latest test of today (last in sorted order)
        today_marks_list = [scaled_marks(r) for r in today_records]
        current_marks = today_marks_list[-1]
        current_tier  = get_tier_info(current_marks, exam_type)
        current_date_str = today.strftime("%d %b %Y")
        # Delta vs previous test before today
        prior_marks = [m for r, m in zip(sorted_records, all_marks) if record_date(r) < today]
        delta_html = ""
        if prior_marks:
            diff = current_marks - prior_marks[-1]
            if diff > 0:
                delta_html = f'<span style="color:#4ade80;font-size:13px;margin-left:8px;">&#9650; +{diff:.1f}</span>'
            elif diff < 0:
                delta_html = f'<span style="color:#f87171;font-size:13px;margin-left:8px;">&#9660; {diff:.1f}</span>'
            else:
                delta_html = '<span style="color:#94a3b8;font-size:13px;margin-left:8px;">&#8212; 0.0</span>'
    else:
        current_marks    = None
        current_tier     = None
        current_date_str = today.strftime("%d %b %Y")
        delta_html       = ""

    # ── Build Current Rating block HTML ──
    if has_today:
        cur_color = current_tier['color']
        current_block_html = f"""
      <div style="
        flex: 1;
        background: linear-gradient(135deg, #161b22 0%, #1e2430 100%);
        border: 1px solid {cur_color}40;
        border-left: 4px solid {cur_color};
        border-radius: 12px;
        padding: 16px 20px;
        position: relative;
        overflow: hidden;
      ">
        <div style="position:absolute;top:-20px;right:-20px;width:80px;height:80px;
                    background:{cur_color}08;border-radius:50%;"></div>
        <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:6px;">
          Today's {exam_label} Rating
        </div>
        <div style="display:flex;align-items:baseline;gap:4px;">
          <span style="font-size:32px;font-weight:800;color:{cur_color};line-height:1.1;
                       text-shadow:0 0 20px {cur_color}30;">{current_marks:.1f}</span>
          <span style="font-size:16px;color:#64748b;font-weight:500;">/ {max_possible}</span>
          {delta_html}
        </div>
        <div style="display:inline-block;margin-top:8px;padding:3px 10px;
                    background:{cur_color}18;border:1px solid {cur_color}35;
                    border-radius:20px;font-size:12px;font-weight:600;color:{cur_color};">
          {current_tier['name']}
        </div>
        <div style="font-size:11px;color:#64748b;margin-top:6px;">&#128197; {current_date_str}</div>
      </div>"""
    else:
        current_block_html = f"""
      <div style="
        flex: 1;
        background: linear-gradient(135deg, #161b22 0%, #1e2430 100%);
        border: 1px solid rgba(148,163,184,0.2);
        border-left: 4px solid #475569;
        border-radius: 12px;
        padding: 16px 20px;
      ">
        <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:6px;">
          Today's {exam_label} Rating
        </div>
        <div style="font-size:22px;font-weight:700;color:#475569;line-height:1.2;">&#8212; / {max_possible}</div>
        <div style="font-size:12px;color:#64748b;margin-top:8px;">No test recorded today</div>
        <div style="font-size:11px;color:#475569;margin-top:4px;">&#128197; {current_date_str}</div>
      </div>"""

    # ── Build Highest Rating block HTML ──
    hi_color = highest_tier['color']
    highest_block_html = f"""
      <div style="
        flex: 1;
        background: linear-gradient(135deg, #161b22 0%, #1a1520 100%);
        border: 1px solid {hi_color}40;
        border-left: 4px solid {hi_color};
        border-radius: 12px;
        padding: 16px 20px;
        position: relative;
        overflow: hidden;
      ">
        <div style="position:absolute;top:-20px;right:-20px;width:80px;height:80px;
                    background:{hi_color}08;border-radius:50%;"></div>
        <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:6px;">
          &#127942; Highest {exam_label} Rating
        </div>
        <div style="display:flex;align-items:baseline;gap:4px;">
          <span style="font-size:32px;font-weight:800;color:{hi_color};line-height:1.1;
                       text-shadow:0 0 20px {hi_color}30;">{highest_marks:.1f}</span>
          <span style="font-size:16px;color:#64748b;font-weight:500;">/ {max_possible}</span>
        </div>
        <div style="display:inline-block;margin-top:8px;padding:3px 10px;
                    background:{hi_color}18;border:1px solid {hi_color}35;
                    border-radius:20px;font-size:12px;font-weight:600;color:{hi_color};">
          {highest_tier['name']}
        </div>
        <div style="font-size:11px;color:#64748b;margin-top:6px;">&#128197; Achieved on {highest_date_str}</div>
      </div>"""

    card_html = f"""
    <div style="display:flex;gap:16px;margin-bottom:16px;font-family:Inter,-apple-system,sans-serif;">
      {current_block_html}
      {highest_block_html}
    </div>
    """
    return card_html


# ─── HIGH-LEVEL DASHBOARD RENDERER ──────────────────────────────────────────

def render_codeforces_dashboard(records, exam_type="Prelims", username=None):
    """
    Renders the complete Codeforces dashboard:
    1. Top controls (Scale Mode, Year selector)
    2. Codeforces Marks Rating Graph with Rank Tiers & Benchmark
    3. Codeforces Activity Heatmap with Brightness/Red color scale
    4. Codeforces 3-Column Statistics Block
    """
    is_prelims = (exam_type.lower() == "prelims")
    title_prefix = "🎯 UPSC Prelims" if is_prelims else "✍️ UPSC Mains"
    scale_label = "200 Marks (GS Paper 1)" if is_prelims else "250 Marks (GS Paper Scale)"
    
    # 1. Header & Controls
    c_left, c_mid, c_right = st.columns([3, 1.5, 1.5])
    with c_left:
        st.markdown(f"#### {title_prefix} Performance Trajectory & Activity")
        st.caption(f"Codeforces Rating system adapted to UPSC Marks • Benchmark: {scale_label}")
    with c_mid:
        scale_mode = st.selectbox(
            "Scale Mode",
            ["Standardized (200/250)", "Raw Marks"],
            key=f"cf_scale_{exam_type}",
            help="Standardize tests of different question counts to the full UPSC paper scale"
        )
    with c_right:
        # Compute available years from records
        years = ["All Time"]
        for r in records:
            d = r.get("date")
            if d:
                y = str(d.year if hasattr(d, "year") else str(d)[:4])
                if y not in years and len(y) == 4:
                    years.append(y)
        selected_year = st.selectbox(
            "Choose year",
            years,
            key=f"cf_yr_{exam_type}",
            help="Filter heatmap by test year"
        )

    # 2. Rating Card (Current + Highest)
    rating_card_html = render_rating_card_html(records, exam_type=exam_type, scale_mode=scale_mode)
    if rating_card_html:
        st.markdown(rating_card_html, unsafe_allow_html=True)

    # 3. Codeforces Marks Graph
    fig = build_codeforces_graph_fig(records, exam_type=exam_type, scale_mode=scale_mode)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # 4. Codeforces Activity Heatmap & 3-Column Stats Block
    heatmap_html = render_codeforces_heatmap_html(records, exam_type=exam_type, selected_year=selected_year)
    # Use components.html so the full grid HTML renders (st.markdown strips complex HTML)
    full_heatmap_page = f"""
    <!DOCTYPE html><html><head>
    <meta charset="utf-8">
    <style>body{{margin:0;padding:0;background:transparent;}}</style>
    </head><body>
    {heatmap_html}
    </body></html>
    """
    components.html(full_heatmap_page, height=420, scrolling=False)

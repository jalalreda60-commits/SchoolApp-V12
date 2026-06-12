"""
dashboard.py — SGS v4  (clean SaaS layout)

Layout
──────
Row 0  : Section label "ÉLÈVES"
Row 1  : 4 student KPI cards  (Total / Payés / Non payés / Créances)
Row 2  : Section labels  "EMPLOYÉS"  "ASSURANCE"  "BÉNÉFICE"
Row 3  : 1 employee + 1 insurance + 1 profit  (each spanning wider)
Charts : Annual profit (full-width), then 3 charts in 2 rows
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QSizePolicy, QPushButton, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from datetime import datetime

try:
    import matplotlib, matplotlib.ticker
    matplotlib.use('Agg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    HAS_MPL = True
except Exception:
    HAS_MPL = False

from models.database import (
    Student, Payment, MonthRecord, Employee, Salary,
    Setting, ExpenseCategory, ExpensePayment, SCHOOL_MONTHS
)
from themes.style import BG_CARD, BORDER, TEXT_MAIN, TEXT_SUB, CLASSES

# ── Colour palette ─────────────────────────────────────────────────────────────
C_STUD  = '#0EA5E9'; C_STUD_BG  = '#F0F9FF'; C_STUD_BD  = '#BAE6FD'
C_EMP   = '#8B5CF6'; C_EMP_BG   = '#F5F3FF'; C_EMP_BD   = '#DDD6FE'
C_INS   = '#F59E0B'; C_INS_BG   = '#FFFBEB'; C_INS_BD   = '#FDE68A'
C_PROF  = '#10B981'; C_PROF_BG  = '#ECFDF5'; C_PROF_BD  = '#A7F3D0'
C_LOSS  = '#EF4444'; C_LOSS_BG  = '#FEF2F2'; C_LOSS_BD  = '#FECACA'
C_WARN  = '#F59E0B'; C_WARN_BG  = '#FFFBEB'; C_WARN_BD  = '#FDE68A'
C_EXP   = '#F43F5E'; C_GRID = '#F1F5F9'

_SCHOOL_CAL  = {'Septembre':9,'Octobre':10,'Novembre':11,'Décembre':12,
                'Janvier':1,'Février':2,'Mars':3,'Avril':4,'Mai':5,'Juin':6}
_CAL_TO_SIDX = {9:0,10:1,11:2,12:3,1:4,2:5,3:6,4:7,5:8,6:9}
_SHORT = ['Sep','Oct','Nov','Déc','Jan','Fév','Mar','Avr','Mai','Jun']
_SHORT_CAL = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']


def _cur_school_month():
    idx = _CAL_TO_SIDX.get(datetime.now().month)
    return SCHOOL_MONTHS[idx] if idx is not None else None


def _fmt(v):
    if abs(v) >= 1_000_000: return f'{v/1_000_000:.2f}M'
    if abs(v) >= 1_000:     return f'{v/1_000:.1f}k'
    return f'{v:.0f}'

def _fmt_mad(v): return _fmt(v) + ' MAD'


def _shadow(w, blur=10, dy=2, alpha=0.07):
    e = QGraphicsDropShadowEffect()
    e.setBlurRadius(blur); e.setOffset(0, dy)
    e.setColor(QColor(0, 0, 0, int(255 * alpha)))
    w.setGraphicsEffect(e); return w


# ── KPI card ──────────────────────────────────────────────────────────────────

class KpiCard(QFrame):
    """Compact SaaS KPI card — white background, coloured left border, no fill."""

    def __init__(self, icon, label, value, accent, subtitle=None):
        super().__init__()
        self.setObjectName('kpi_card')
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(78 if not subtitle else 90)
        self._accent = accent
        self._set_style(False)
        _shadow(self)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(12)

        # Icon circle
        ico = QLabel(icon)
        ico.setFixedSize(34, 34)
        ico.setAlignment(Qt.AlignCenter)
        ico.setStyleSheet(
            f'background:{self._tint(accent)};'
            f'border-radius:17px;font-size:15px;'
        )

        # Text
        txt = QVBoxLayout(); txt.setSpacing(1)
        self._val_lbl = QLabel(str(value))
        self._val_lbl.setStyleSheet(
            f'color:{accent};font-size:18px;font-weight:800;background:transparent;'
        )
        lbl = QLabel(label)
        lbl.setStyleSheet(
            'color:#64748B;font-size:10px;font-weight:600;'
            'background:transparent;letter-spacing:0.2px;'
        )
        txt.addWidget(self._val_lbl)
        txt.addWidget(lbl)
        if subtitle:
            s = QLabel(subtitle)
            s.setStyleSheet('color:#94A3B8;font-size:8px;background:transparent;')
            txt.addWidget(s)

        row.addWidget(ico)
        row.addLayout(txt)
        row.addStretch()

    def _set_style(self, hover):
        bg = '#F8FAFC' if hover else 'white'
        self.setStyleSheet(f'''
            QFrame#kpi_card {{
                background:{bg};
                border:1px solid #E2E8F0;
                border-left:4px solid {self._accent};
                border-radius:10px;
            }}
        ''')

    @staticmethod
    def _tint(hex_col):
        try:
            r=int(hex_col[1:3],16); g=int(hex_col[3:5],16); b=int(hex_col[5:7],16)
            r=r+(255-r)//3; g=g+(255-g)//3; b=b+(255-b)//3
            return f'#{r:02X}{g:02X}{b:02X}'
        except: return '#F1F5F9'

    def enterEvent(self, e): self._set_style(True);  super().enterEvent(e)
    def leaveEvent(self, e): self._set_style(False); super().leaveEvent(e)
    def update_value(self, v): self._val_lbl.setText(str(v))


def _sec_lbl(text):
    l = QLabel(text)
    l.setStyleSheet(
        'color:#94A3B8;font-size:9px;font-weight:700;'
        'letter-spacing:1.4px;background:transparent;padding:6px 2px 2px 2px;'
    )
    return l


def _hline():
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setStyleSheet('color:#E2E8F0;background:#E2E8F0;max-height:1px;margin:2px 0;')
    return f


def _chart_card(title, subtitle=''):
    frame = QFrame()
    frame.setStyleSheet(
        'QFrame{background:white;border:1px solid #E2E8F0;border-radius:12px;}'
    )
    _shadow(frame, blur=12, dy=3, alpha=0.05)
    frame.setMinimumHeight(240)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 12, 16, 10)
    lay.setSpacing(4)
    # header
    hh = QHBoxLayout(); hh.setSpacing(6)
    t = QLabel(title)
    t.setStyleSheet('color:#1E293B;font-size:11px;font-weight:700;background:transparent;')
    hh.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setStyleSheet('color:#94A3B8;font-size:9px;background:transparent;')
        hh.addWidget(s)
    hh.addStretch()
    lay.addLayout(hh)
    inner = QVBoxLayout(); inner.setContentsMargins(0,0,0,0)
    lay.addLayout(inner, 1)
    return frame, inner


# ══════════════════════════════════════════════════════════════════════════════
#  DashboardWidget
# ══════════════════════════════════════════════════════════════════════════════

class DashboardWidget(QWidget):

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.setStyleSheet('background:transparent;')
        self._cache = {}
        self._kpi_refs = {}   # name → KpiCard (for live update)
        self._setup_ui()
        QTimer.singleShot(100, self._load_data)
        self._timer = QTimer(self)
        self._timer.setInterval(90_000)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    # ── Build UI (once) ───────────────────────────────────────────────────────

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            'QScrollArea{border:none;background:transparent;}'
            'QScrollBar:vertical{width:5px;background:#F8FAFC;border-radius:3px;}'
            'QScrollBar::handle:vertical{background:#CBD5E1;border-radius:3px;min-height:20px;}'
        )
        root = QWidget(); root.setStyleSheet('background:transparent;')
        self._vl = QVBoxLayout(root)
        self._vl.setContentsMargins(22, 14, 22, 24)
        self._vl.setSpacing(8)

        # ── Refresh button (minimal top bar) ──────────────────────────────────
        bar = QHBoxLayout(); bar.addStretch()
        btn = QPushButton('↺  Actualiser')
        btn.setFixedHeight(30)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            'QPushButton{background:white;color:#475569;border:1px solid #E2E8F0;'
            'border-radius:7px;padding:0 14px;font-size:11px;font-weight:600;}'
            'QPushButton:hover{background:#F8FAFC;}'
        )
        btn.clicked.connect(self.refresh)
        bar.addWidget(btn)
        self._vl.addLayout(bar)

        # ── KPI section: ÉLÈVES ───────────────────────────────────────────────
        self._vl.addWidget(_sec_lbl('👤  ÉLÈVES'))
        self._stud_row = QHBoxLayout(); self._stud_row.setSpacing(10)
        self._vl.addLayout(self._stud_row)

        # ── KPI section: EMPLOYÉS / ASSURANCE / BÉNÉFICE ─────────────────────
        self._vl.addSpacing(4)
        grp2_lbl = QHBoxLayout(); grp2_lbl.setSpacing(0)
        for txt, stretch in [('👔  EMPLOYÉS', 1), ('🛡  ASSURANCE', 1), ('📈  BÉNÉFICE', 2)]:
            grp2_lbl.addWidget(_sec_lbl(txt), stretch)
        self._vl.addLayout(grp2_lbl)

        self._grp2_row = QHBoxLayout(); self._grp2_row.setSpacing(10)
        self._vl.addLayout(self._grp2_row)

        # ── Charts ────────────────────────────────────────────────────────────
        if HAS_MPL:
            self._vl.addWidget(_hline())

            # Annual profit full width
            self._annual = AnnualProfitChart(self.session)
            self._vl.addWidget(self._annual)

            # Row A: paid students | paid expenses
            ra = QHBoxLayout(); ra.setSpacing(10)
            self._ch1f, self._ch1l = _chart_card(
                '✅  Élèves payés par mois', 'Nombre — mois scolaire')
            self._ch2f, self._ch2l = _chart_card(
                '💸  Dépenses payées par mois', 'Montant — mois scolaire')
            ra.addWidget(self._ch1f, 1); ra.addWidget(self._ch2f, 1)
            self._vl.addLayout(ra)

            # Row B: students per month | class pie
            rb = QHBoxLayout(); rb.setSpacing(10)
            self._ch3f, self._ch3l = _chart_card(
                '🎓  Élèves inscrits par mois', 'Total — mois scolaire')
            self._ch4f, self._ch4l = _chart_card(
                '📊  Répartition par classe', 'Élèves actifs')
            rb.addWidget(self._ch3f, 3); rb.addWidget(self._ch4f, 2)
            self._vl.addLayout(rb)

        self._vl.addStretch()
        scroll.setWidget(root)
        ol = QVBoxLayout(self)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.addWidget(scroll)

    # ── Clear helpers ─────────────────────────────────────────────────────────

    def _clear_row(self, row_layout):
        for i in reversed(range(row_layout.count())):
            item = row_layout.itemAt(i)
            if item and item.widget(): item.widget().setParent(None)

    def _clear_chart(self, lay):
        for i in reversed(range(lay.count())):
            w = lay.itemAt(i).widget()
            if w: w.setParent(None)

    # ── Load + render ─────────────────────────────────────────────────────────

    def _load_data(self):
        self.session.expire_all()
        try:    self._render()
        except: import traceback; traceback.print_exc()

    def _render(self):
        cy = datetime.now().year
        settings = {s.key: s.value for s in self.session.query(Setting).all()}
        sy = settings.get('school_year', '2024-25')
        try: sy0, sy1 = int(sy.split('-')[0]), int(sy.split('-')[0]) + 1
        except: sy0, sy1 = cy - 1, cy

        month = _cur_school_month()
        pyear = (sy0 if _SCHOOL_CAL.get(month, 1) >= 9 else sy1) if month else cy

        # ── Students ──────────────────────────────────────────────────────────
        students = self.session.query(Student).filter_by(active=True).all()
        n_total  = len(students)
        sid_map  = {s.id: s for s in students}

        recs = {}
        if month:
            for r in self.session.query(MonthRecord).filter_by(
                month_name=month, school_year=sy).all():
                recs[r.student_id] = r

        n_paid   = sum(1 for s in students
                       if recs.get(s.id) and recs[s.id].status == 'paid')
        n_unpaid = sum(1 for s in students
                       if recs.get(s.id) and recs[s.id].status == 'unpaid')
        all_unpaid_recs = self.session.query(MonthRecord).filter_by(
            status='unpaid', school_year=sy).all()
        outstanding = sum(
            (sid_map[r.student_id].monthly_fee or 0)
            + ((sid_map[r.student_id].transport_fee or 0)
               if sid_map[r.student_id].has_transport else 0)
            for r in all_unpaid_recs if r.student_id in sid_map
        )
        debt_col = C_LOSS if outstanding > 50000 else (C_WARN if outstanding > 0 else C_PROF)

        # ── Employees ─────────────────────────────────────────────────────────
        n_emp = self.session.query(Employee).filter_by(active=True).count()

        # ── Insurance (school year) ────────────────────────────────────────────
        ins_total = sum(
            p.amount or 0.0
            for p in self.session.query(Payment).filter_by(
                payment_type='insurance', school_year=sy).all()
        )

        # ── Revenue (current month, no insurance) ─────────────────────────────
        collected = sum(
            p.amount or 0
            for p in self.session.query(Payment).filter(
                Payment.payment_type.in_(['monthly', 'transport']),
                Payment.month == month,
                Payment.school_year == sy,
            ).all()
        ) if month else 0.0

        # ── Expenses paid (current month) ─────────────────────────────────────
        exp_paid = sum(
            ep.amount or 0
            for ep in self.session.query(ExpensePayment).filter_by(
                month=month, year=pyear).all()
        ) if month else 0.0

        # ── Salaries paid (current month) ─────────────────────────────────────
        sal_amt = 0.0
        if month:
            for sal in self.session.query(Salary).filter_by(month=month).all():
                if not getattr(sal, 'paid', False): continue
                yr = getattr(sal, 'year', None)
                if yr and yr not in (sy0, sy1): continue
                sal_amt += sal.net_salary or getattr(sal, 'total', 0) or 0.0

        # ── Profit ────────────────────────────────────────────────────────────
        # Formula: Student Payments (monthly+transport) − Paid Expenses − Paid Salaries
        profit   = collected - exp_paid - sal_amt
        p_col    = C_PROF if profit >= 0 else C_LOSS
        p_sign   = '+' if profit > 0 else ''
        p_sub    = f'Rev {_fmt_mad(collected)} − Dep {_fmt_mad(exp_paid)} − Sal {_fmt_mad(sal_amt)}'

        # ── Populate KPI rows ─────────────────────────────────────────────────
        self._clear_row(self._stud_row)
        self._stud_row.addWidget(KpiCard('👥', 'Total élèves',      n_total,              C_STUD))
        self._stud_row.addWidget(KpiCard('✅', 'Payés ce mois',     n_paid,               C_PROF))
        self._stud_row.addWidget(KpiCard('⏳', 'Non payés ce mois', n_unpaid,             C_LOSS))
        self._stud_row.addWidget(KpiCard('💳', 'Créances totales',  _fmt_mad(outstanding), debt_col))

        self._clear_row(self._grp2_row)
        self._grp2_row.addWidget(
            KpiCard('👔', 'Total employés', n_emp, C_EMP, subtitle='Employés actifs'))
        self._grp2_row.addWidget(
            KpiCard('🛡', 'Assurance (année)', _fmt_mad(ins_total), C_INS,
                    subtitle=f'{sy}  •  Nov – Jun'))
        self._grp2_row.addWidget(
            KpiCard('📈', 'Bénéfice du mois', p_sign + _fmt_mad(profit), p_col,
                    subtitle=p_sub), )
        self._grp2_row.addWidget(
            KpiCard('📈', 'Bénéfice du mois', p_sign + _fmt_mad(profit), p_col,
                    subtitle=p_sub))

        # Remove duplicate — second addWidget shadows the first; fix below
        # (use stretch to balance the row)

        # ── Charts ────────────────────────────────────────────────────────────
        if HAS_MPL:
            self._build_cache(sy, sy0, sy1)
            if hasattr(self, '_annual'): self._annual.refresh()
            self._draw_paid_students()
            self._draw_paid_expenses()
            self._draw_registrations()
            self._draw_class_pie()

    def _render(self):  # noqa: redefined — clean version below replaces above
        cy = datetime.now().year
        settings = {s.key: s.value for s in self.session.query(Setting).all()}
        sy = settings.get('school_year', '2024-25')
        try: sy0, sy1 = int(sy.split('-')[0]), int(sy.split('-')[0]) + 1
        except: sy0, sy1 = cy - 1, cy

        month = _cur_school_month()
        pyear = (sy0 if _SCHOOL_CAL.get(month, 1) >= 9 else sy1) if month else cy

        students = self.session.query(Student).filter_by(active=True).all()
        n_total  = len(students)
        sid_map  = {s.id: s for s in students}

        recs = {}
        if month:
            for r in self.session.query(MonthRecord).filter_by(
                    month_name=month, school_year=sy).all():
                recs[r.student_id] = r

        n_paid   = sum(1 for s in students
                       if recs.get(s.id) and recs[s.id].status == 'paid')
        n_unpaid = sum(1 for s in students
                       if recs.get(s.id) and recs[s.id].status == 'unpaid')

        all_unpaid_recs = self.session.query(MonthRecord).filter_by(
            status='unpaid', school_year=sy).all()
        outstanding = sum(
            (sid_map[r.student_id].monthly_fee or 0)
            + ((sid_map[r.student_id].transport_fee or 0)
               if sid_map[r.student_id].has_transport else 0)
            for r in all_unpaid_recs if r.student_id in sid_map
        )
        debt_col = C_LOSS if outstanding > 50000 else (C_WARN if outstanding > 0 else C_PROF)

        n_emp = self.session.query(Employee).filter_by(active=True).count()

        ins_total = sum(
            p.amount or 0.0
            for p in self.session.query(Payment).filter_by(
                payment_type='insurance', school_year=sy).all()
        )

        collected = 0.0
        if month:
            for p in self.session.query(Payment).filter(
                    Payment.payment_type.in_(['monthly', 'transport']),
                    Payment.month == month,
                    Payment.school_year == sy).all():
                collected += p.amount or 0

        exp_paid = 0.0
        if month:
            for ep in self.session.query(ExpensePayment).filter_by(
                    month=month, year=pyear).all():
                exp_paid += ep.amount or 0

        sal_amt = 0.0
        if month:
            for sal in self.session.query(Salary).filter_by(month=month).all():
                if not getattr(sal, 'paid', False): continue
                yr = getattr(sal, 'year', None)
                if yr and yr not in (sy0, sy1): continue
                sal_amt += sal.net_salary or getattr(sal, 'total', 0) or 0.0

        profit = collected - exp_paid - sal_amt
        p_col  = C_PROF if profit >= 0 else C_LOSS
        p_sign = '+' if profit > 0 else ''
        p_sub  = (f'Rev {_fmt_mad(collected)} − '
                  f'Dep {_fmt_mad(exp_paid)} − '
                  f'Sal {_fmt_mad(sal_amt)}')

        # ── KPI Row 1: Students (4 equal cards) ───────────────────────────────
        self._clear_row(self._stud_row)
        for icon, lbl, val, col in [
            ('👥', 'Total élèves',       n_total,               C_STUD),
            ('✅', 'Payés ce mois',      n_paid,                C_PROF),
            ('⏳', 'Non payés ce mois',  n_unpaid,              C_LOSS),
            ('💳', 'Créances totales',   _fmt_mad(outstanding), debt_col),
        ]:
            self._stud_row.addWidget(KpiCard(icon, lbl, val, col))

        # ── KPI Row 2: Employee (1) + Insurance (1) + Profit (2 wide) ─────────
        self._clear_row(self._grp2_row)
        self._grp2_row.addWidget(
            KpiCard('👔', 'Total employés', n_emp, C_EMP,
                    subtitle='Employés actifs'), 1)
        self._grp2_row.addWidget(
            KpiCard('🛡', 'Assurance (année)', _fmt_mad(ins_total), C_INS,
                    subtitle=f'{sy}  •  Nov – Jun'), 1)
        self._grp2_row.addWidget(
            KpiCard('📈', 'Bénéfice du mois', p_sign + _fmt_mad(profit), p_col,
                    subtitle=p_sub), 2)

        # ── Charts ────────────────────────────────────────────────────────────
        if HAS_MPL:
            self._build_cache(sy, sy0, sy1)
            if hasattr(self, '_annual'): self._annual.refresh()
            self._draw_paid_students()
            self._draw_paid_expenses()
            self._draw_registrations()
            self._draw_class_pie()

    # ── Chart cache ───────────────────────────────────────────────────────────

    def _build_cache(self, sy, sy0, sy1):
        paid_count = [0]   * 10
        exp_total  = [0.0] * 10
        reg_count  = [0]   * 10

        for r in self.session.query(MonthRecord).filter_by(
                status='paid', school_year=sy).all():
            try: paid_count[SCHOOL_MONTHS.index(r.month_name)] += 1
            except: pass

        for ep in self.session.query(ExpensePayment).all():
            try:
                idx = SCHOOL_MONTHS.index(ep.month)
                if ep.year == (sy0 if idx <= 3 else sy1):
                    exp_total[idx] += ep.amount or 0
            except: pass

        for r in self.session.query(MonthRecord).filter(
                MonthRecord.school_year == sy,
                MonthRecord.status != 'nan').all():
            try: reg_count[SCHOOL_MONTHS.index(r.month_name)] += 1
            except: pass

        self._cache = {'paid': paid_count, 'exp': exp_total, 'reg': reg_count}

    # ── Chart drawing helpers ─────────────────────────────────────────────────

    def _fig(self, w=6, h=2.4):
        fig = Figure(figsize=(w, h), facecolor='white')
        fig.subplots_adjust(left=0.09, right=0.97, top=0.82, bottom=0.18)
        return fig

    def _ax_style(self, ax, labels, y_int=False):
        ax.set_facecolor('#FAFAFA')
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=7.5)
        for t in ax.get_xticklabels(): t.set_color('#64748B')
        ax.yaxis.set_tick_params(labelcolor='#64748B', labelsize=7.5)
        fmt = (matplotlib.ticker.FuncFormatter(lambda v, _: f'{int(v)}') if y_int else
               matplotlib.ticker.FuncFormatter(
                   lambda v, _: f'{v/1000:.0f}k' if abs(v) >= 1000 else f'{v:.0f}'))
        ax.yaxis.set_major_formatter(fmt)
        for sp in ax.spines.values(): sp.set_visible(False)
        ax.yaxis.grid(True, color='#F1F5F9', linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)

    def _canvas(self, fig, lay):
        self._clear_chart(lay)
        cv = FigureCanvas(fig)
        cv.setStyleSheet('background:white;')
        lay.addWidget(cv)

    # ── Chart 1: Paid students per school month ───────────────────────────────

    def _draw_paid_students(self):
        d = self._cache.get('paid', [0]*10)
        fig = self._fig(); ax = fig.add_subplot(111)
        bars = ax.bar(range(10), d, color=C_STUD, width=0.55, zorder=3, alpha=0.85)
        for bar, v in zip(bars, d):
            if v > 0:
                ax.text(bar.get_x()+bar.get_width()/2, v+0.3, str(v),
                        ha='center', fontsize=6.5, fontweight='700',
                        color=C_STUD, zorder=5)
        self._ax_style(ax, _SHORT, y_int=True)
        ax.set_ylim(0, max(d)*1.2+1 if any(d) else 5)
        ax.set_title('Élèves payés / mois', fontsize=8.5, fontweight='700',
                     color='#1E293B', pad=4, loc='left')
        fig.tight_layout(pad=0.7)
        self._canvas(fig, self._ch1l)

    # ── Chart 2: Paid expenses per school month ───────────────────────────────

    def _draw_paid_expenses(self):
        d = self._cache.get('exp', [0.0]*10)
        fig = self._fig(); ax = fig.add_subplot(111)
        bars = ax.bar(range(10), d, color=C_EXP, width=0.55, zorder=3, alpha=0.82)
        mx = max(d) if any(d) else 1
        for bar, v in zip(bars, d):
            if v > 0:
                lbl = f'{v/1000:.1f}k' if v >= 1000 else f'{v:.0f}'
                ax.text(bar.get_x()+bar.get_width()/2, v+mx*0.015+1, lbl,
                        ha='center', fontsize=6.5, fontweight='700',
                        color=C_EXP, zorder=5)
        self._ax_style(ax, _SHORT)
        ax.set_ylim(0, mx*1.2+1)
        ax.set_title('Dépenses payées / mois', fontsize=8.5, fontweight='700',
                     color='#1E293B', pad=4, loc='left')
        fig.tight_layout(pad=0.7)
        self._canvas(fig, self._ch2l)

    # ── Chart 3: Students per month (registered) ──────────────────────────────

    def _draw_registrations(self):
        d = self._cache.get('reg', [0]*10)
        xs = range(10)
        fig = self._fig(w=8); ax = fig.add_subplot(111)
        ax.fill_between(xs, d, alpha=0.10, color=C_STUD)
        ax.plot(xs, d, color=C_STUD, lw=2.2, zorder=3,
                marker='o', ms=5, markerfacecolor='white',
                markeredgewidth=2, markeredgecolor=C_STUD)
        for i, v in enumerate(d):
            if v > 0:
                ax.text(i, v + max(d)*0.04+0.2, str(v),
                        ha='center', fontsize=6.5, fontweight='700',
                        color=C_STUD, zorder=5)
        self._ax_style(ax, _SHORT, y_int=True)
        ax.set_ylim(0, max(d)*1.22+1 if any(d) else 5)
        ax.set_title('Élèves inscrits / mois', fontsize=8.5, fontweight='700',
                     color='#1E293B', pad=4, loc='left')
        fig.tight_layout(pad=0.7)
        self._canvas(fig, self._ch3l)

    # ── Chart 4: Class breakdown pie ──────────────────────────────────────────

    def _draw_class_pie(self):
        counts, labels = [], []
        for cls in CLASSES:
            n = self.session.query(Student).filter_by(
                class_name=cls, active=True).count()
            if n: counts.append(n); labels.append(cls)
        if not counts: counts, labels = [1], ['Aucun']

        pal = ['#0EA5E9','#8B5CF6','#10B981','#F59E0B','#EF4444',
               '#6366F1','#14B8A6','#EC4899','#22C55E','#F97316']
        fig = Figure(figsize=(4, 2.4), facecolor='white')
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        ax = fig.add_subplot(111)
        ax.pie(counts, labels=labels, autopct='%1.0f%%',
               colors=pal[:len(counts)],
               textprops={'fontsize':7,'color':'#374151'},
               pctdistance=0.78,
               wedgeprops={'linewidth':1.5,'edgecolor':'white'})
        self._canvas(fig, self._ch4l)

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh(self):
        self._cache = {}
        self._load_data()

    def _render(self):
        cy = datetime.now().year
        settings = {s.key: s.value for s in self.session.query(Setting).all()}
        sy = settings.get('school_year', '2024-25')
        try: sy0, sy1 = int(sy.split('-')[0]), int(sy.split('-')[0]) + 1
        except: sy0, sy1 = cy - 1, cy

        month = _cur_school_month()
        pyear = (sy0 if _SCHOOL_CAL.get(month, 1) >= 9 else sy1) if month else cy

        students = self.session.query(Student).filter_by(active=True).all()
        n_total  = len(students)
        sid_map  = {s.id: s for s in students}

        recs = {}
        if month:
            for r in self.session.query(MonthRecord).filter_by(
                    month_name=month, school_year=sy).all():
                recs[r.student_id] = r

        n_paid   = sum(1 for s in students
                       if recs.get(s.id) and recs[s.id].status == 'paid')
        n_unpaid = sum(1 for s in students
                       if recs.get(s.id) and recs[s.id].status == 'unpaid')

        all_unpaid_recs = self.session.query(MonthRecord).filter_by(
            status='unpaid', school_year=sy).all()
        outstanding = sum(
            (sid_map[r.student_id].monthly_fee or 0)
            + ((sid_map[r.student_id].transport_fee or 0)
               if sid_map[r.student_id].has_transport else 0)
            for r in all_unpaid_recs if r.student_id in sid_map
        )
        debt_col = C_LOSS if outstanding > 50000 else (C_WARN if outstanding > 0 else C_PROF)

        n_emp = self.session.query(Employee).filter_by(active=True).count()

        ins_total = sum(
            p.amount or 0.0
            for p in self.session.query(Payment).filter_by(
                payment_type='insurance', school_year=sy).all()
        )

        collected = 0.0
        if month:
            for p in self.session.query(Payment).filter(
                    Payment.payment_type.in_(['monthly', 'transport']),
                    Payment.month == month,
                    Payment.school_year == sy).all():
                collected += p.amount or 0

        exp_paid = 0.0
        if month:
            for ep in self.session.query(ExpensePayment).filter_by(
                    month=month, year=pyear).all():
                exp_paid += ep.amount or 0

        sal_amt = 0.0
        if month:
            for sal in self.session.query(Salary).filter_by(month=month).all():
                if not getattr(sal, 'paid', False): continue
                yr = getattr(sal, 'year', None)
                if yr and yr not in (sy0, sy1): continue
                sal_amt += sal.net_salary or getattr(sal, 'total', 0) or 0.0

        profit = collected - exp_paid - sal_amt
        p_col  = C_PROF if profit >= 0 else C_LOSS
        p_sign = '+' if profit > 0 else ''
        p_sub  = (f'Rev {_fmt_mad(collected)} − '
                  f'Dep {_fmt_mad(exp_paid)} − '
                  f'Sal {_fmt_mad(sal_amt)}')

        # ── KPI Row 1: Students (4 equal cards) ───────────────────────────────
        self._clear_row(self._stud_row)
        for icon, lbl, val, col in [
            ('👥', 'Total élèves',       n_total,               C_STUD),
            ('✅', 'Payés ce mois',      n_paid,                C_PROF),
            ('⏳', 'Non payés ce mois',  n_unpaid,              C_LOSS),
            ('💳', 'Créances totales',   _fmt_mad(outstanding), debt_col),
        ]:
            self._stud_row.addWidget(KpiCard(icon, lbl, val, col))

        # ── KPI Row 2: Employee (1) + Insurance (1) + Profit (2 wide) ─────────
        self._clear_row(self._grp2_row)
        self._grp2_row.addWidget(
            KpiCard('👔', 'Total employés', n_emp, C_EMP,
                    subtitle='Employés actifs'), 1)
        self._grp2_row.addWidget(
            KpiCard('🛡', 'Assurance (année)', _fmt_mad(ins_total), C_INS,
                    subtitle=f'{sy}  •  Nov – Jun'), 1)
        self._grp2_row.addWidget(
            KpiCard('📈', 'Bénéfice du mois', p_sign + _fmt_mad(profit), p_col,
                    subtitle=p_sub), 2)

        # ── Charts ────────────────────────────────────────────────────────────
        if HAS_MPL:
            self._build_cache(sy, sy0, sy1)
            if hasattr(self, '_annual'): self._annual.refresh()
            self._draw_paid_students()
            self._draw_paid_expenses()
            self._draw_registrations()
            self._draw_class_pie()

    # ── Chart cache ───────────────────────────────────────────────────────────

    def _build_cache(self, sy, sy0, sy1):
        paid_count = [0]   * 10
        exp_total  = [0.0] * 10
        reg_count  = [0]   * 10

        for r in self.session.query(MonthRecord).filter_by(
                status='paid', school_year=sy).all():
            try: paid_count[SCHOOL_MONTHS.index(r.month_name)] += 1
            except: pass

        for ep in self.session.query(ExpensePayment).all():
            try:
                idx = SCHOOL_MONTHS.index(ep.month)
                if ep.year == (sy0 if idx <= 3 else sy1):
                    exp_total[idx] += ep.amount or 0
            except: pass

        for r in self.session.query(MonthRecord).filter(
                MonthRecord.school_year == sy,
                MonthRecord.status != 'nan').all():
            try: reg_count[SCHOOL_MONTHS.index(r.month_name)] += 1
            except: pass

        self._cache = {'paid': paid_count, 'exp': exp_total, 'reg': reg_count}

    # ── Chart drawing helpers ─────────────────────────────────────────────────

    def _fig(self, w=6, h=2.4):
        fig = Figure(figsize=(w, h), facecolor='white')
        fig.subplots_adjust(left=0.09, right=0.97, top=0.82, bottom=0.18)
        return fig

    def _ax_style(self, ax, labels, y_int=False):
        ax.set_facecolor('#FAFAFA')
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=7.5)
        for t in ax.get_xticklabels(): t.set_color('#64748B')
        ax.yaxis.set_tick_params(labelcolor='#64748B', labelsize=7.5)
        fmt = (matplotlib.ticker.FuncFormatter(lambda v, _: f'{int(v)}') if y_int else
               matplotlib.ticker.FuncFormatter(
                   lambda v, _: f'{v/1000:.0f}k' if abs(v) >= 1000 else f'{v:.0f}'))
        ax.yaxis.set_major_formatter(fmt)
        for sp in ax.spines.values(): sp.set_visible(False)
        ax.yaxis.grid(True, color='#F1F5F9', linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)

    def _canvas(self, fig, lay):
        self._clear_chart(lay)
        cv = FigureCanvas(fig)
        cv.setStyleSheet('background:white;')
        lay.addWidget(cv)

    # ── Chart 1: Paid students per school month ───────────────────────────────

    def _draw_paid_students(self):
        d = self._cache.get('paid', [0]*10)
        fig = self._fig(); ax = fig.add_subplot(111)
        bars = ax.bar(range(10), d, color=C_STUD, width=0.55, zorder=3, alpha=0.85)
        for bar, v in zip(bars, d):
            if v > 0:
                ax.text(bar.get_x()+bar.get_width()/2, v+0.3, str(v),
                        ha='center', fontsize=6.5, fontweight='700',
                        color=C_STUD, zorder=5)
        self._ax_style(ax, _SHORT, y_int=True)
        ax.set_ylim(0, max(d)*1.2+1 if any(d) else 5)
        ax.set_title('Élèves payés / mois', fontsize=8.5, fontweight='700',
                     color='#1E293B', pad=4, loc='left')
        fig.tight_layout(pad=0.7)
        self._canvas(fig, self._ch1l)

    # ── Chart 2: Paid expenses per school month ───────────────────────────────

    def _draw_paid_expenses(self):
        d = self._cache.get('exp', [0.0]*10)
        fig = self._fig(); ax = fig.add_subplot(111)
        bars = ax.bar(range(10), d, color=C_EXP, width=0.55, zorder=3, alpha=0.82)
        mx = max(d) if any(d) else 1
        for bar, v in zip(bars, d):
            if v > 0:
                lbl = f'{v/1000:.1f}k' if v >= 1000 else f'{v:.0f}'
                ax.text(bar.get_x()+bar.get_width()/2, v+mx*0.015+1, lbl,
                        ha='center', fontsize=6.5, fontweight='700',
                        color=C_EXP, zorder=5)
        self._ax_style(ax, _SHORT)
        ax.set_ylim(0, mx*1.2+1)
        ax.set_title('Dépenses payées / mois', fontsize=8.5, fontweight='700',
                     color='#1E293B', pad=4, loc='left')
        fig.tight_layout(pad=0.7)
        self._canvas(fig, self._ch2l)

    # ── Chart 3: Students per month (registered) ──────────────────────────────

    def _draw_registrations(self):
        d = self._cache.get('reg', [0]*10)
        xs = range(10)
        fig = self._fig(w=8); ax = fig.add_subplot(111)
        ax.fill_between(xs, d, alpha=0.10, color=C_STUD)
        ax.plot(xs, d, color=C_STUD, lw=2.2, zorder=3,
                marker='o', ms=5, markerfacecolor='white',
                markeredgewidth=2, markeredgecolor=C_STUD)
        for i, v in enumerate(d):
            if v > 0:
                ax.text(i, v + max(d)*0.04+0.2, str(v),
                        ha='center', fontsize=6.5, fontweight='700',
                        color=C_STUD, zorder=5)
        self._ax_style(ax, _SHORT, y_int=True)
        ax.set_ylim(0, max(d)*1.22+1 if any(d) else 5)
        ax.set_title('Élèves inscrits / mois', fontsize=8.5, fontweight='700',
                     color='#1E293B', pad=4, loc='left')
        fig.tight_layout(pad=0.7)
        self._canvas(fig, self._ch3l)

    # ── Chart 4: Class breakdown pie ──────────────────────────────────────────

    def _draw_class_pie(self):
        counts, labels = [], []
        for cls in CLASSES:
            n = self.session.query(Student).filter_by(
                class_name=cls, active=True).count()
            if n: counts.append(n); labels.append(cls)
        if not counts: counts, labels = [1], ['Aucun']

        pal = ['#0EA5E9','#8B5CF6','#10B981','#F59E0B','#EF4444',
               '#6366F1','#14B8A6','#EC4899','#22C55E','#F97316']
        fig = Figure(figsize=(4, 2.4), facecolor='white')
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        ax = fig.add_subplot(111)
        ax.pie(counts, labels=labels, autopct='%1.0f%%',
               colors=pal[:len(counts)],
               textprops={'fontsize':7,'color':'#374151'},
               pctdistance=0.78,
               wedgeprops={'linewidth':1.5,'edgecolor':'white'})
        self._canvas(fig, self._ch4l)

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh(self):
        self._cache = {}
        self._load_data()


class AnnualProfitChart(QWidget):
    """
    Full-width Monthly Profit Evolution chart — Jan to Dec.

    Formula per calendar month:
        Profit = Revenue(monthly + transport) − Expenses − Salaries
        Insurance is EXCLUDED.

    Features
    ─────────
    • 12-month calendar bar chart (Jan–Dec)
    • Cumulative profit dashed line overlay
    • Current month highlighted with indigo border + ▼ marker
    • Future months greyed out (no phantom projections)
    • Value labels on every meaningful bar
    • Summary stats row: best month / worst month / YTD cumulative
    • Year selector (current year ± 3)
    • Manual ↺ refresh button + timestamp
    • Auto-refresh every 60 s via QTimer (re-queries DB silently)
    • DashboardWidget calls .refresh() after every payment/expense/salary event
    • Hover tooltip via mpl motion_notify_event (shows breakdown)
    """

    AUTO_REFRESH_MS = 60_000   # 1 minute

    def __init__(self, session):
        super().__init__()
        self.session   = session
        self._canvas   = None
        self._fig      = None
        self._bars     = []
        self._data     = {}     # cached: {year: (rev, exp, sal, prf)}
        self.setStyleSheet('background:transparent;')
        self._build_ui()
        # Defer first draw so the widget is fully shown before matplotlib renders
        QTimer.singleShot(150, self.refresh)
        # Auto-refresh timer
        self._timer = QTimer(self)
        self._timer.setInterval(self.AUTO_REFRESH_MS)
        self._timer.timeout.connect(self._silent_refresh)
        self._timer.start()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Card shell ────────────────────────────────────────────────────────
        self._card = QFrame()
        self._card.setStyleSheet(
            f'QFrame{{'
            f'background:{BG_CARD};'
            f'border:1px solid {BORDER};'
            f'border-radius:12px;'
            f'}}'
        )
        self._card.setMinimumHeight(340)
        card_lay = QVBoxLayout(self._card)
        card_lay.setContentsMargins(18, 14, 18, 12)
        card_lay.setSpacing(8)

        # ── Header row ────────────────────────────────────────────────────────
        hdr = QHBoxLayout(); hdr.setSpacing(10)

        # Icon + title stack
        icon_lbl = QLabel('📈')
        icon_lbl.setFixedSize(36, 36)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(
            f'background:{SUCCESS_LIGHT};border-radius:10px;font-size:17px;'
        )

        title_col = QVBoxLayout(); title_col.setSpacing(1)
        t1 = QLabel('Évolution du Bénéfice Mensuel')
        t1.setStyleSheet(
            f'color:{TEXT_MAIN};font-size:14px;font-weight:800;background:transparent;'
        )
        t2 = QLabel(
            'Revenus + Transport  −  Dépenses  −  Salaires   ·   '
            'Assurance exclue   ·   Jan – Déc'
        )
        t2.setStyleSheet(
            f'color:{TEXT_SUB};font-size:9.5px;background:transparent;'
        )
        title_col.addWidget(t1); title_col.addWidget(t2)

        hdr.addWidget(icon_lbl)
        hdr.addLayout(title_col)
        hdr.addStretch()

        # Year selector
        _lbl_yr = QLabel('Année :')
        _lbl_yr.setStyleSheet(
            f'color:{TEXT_SUB};font-size:11px;font-weight:600;background:transparent;'
        )
        combo_css = (
            f'QComboBox{{background:{PRIMARY_LIGHT};border:1.5px solid {PRIMARY}33;'
            f'border-radius:8px;color:{PRIMARY};padding:3px 10px;'
            f'font-size:12px;font-weight:700;min-width:80px;}}'
            f'QComboBox::drop-down{{border:none;width:18px;}}'
            f'QComboBox QAbstractItemView{{background:white;border:1px solid {BORDER};'
            f'color:{TEXT_MAIN};outline:none;border-radius:6px;}}'
            f'QComboBox QAbstractItemView::item{{padding:6px 12px;}}'
            f'QComboBox QAbstractItemView::item:selected'
            f'{{background:{PRIMARY_LIGHT};color:{PRIMARY};}}'
        )
        self._yr_combo = QComboBox()
        self._yr_combo.setStyleSheet(combo_css)
        self._yr_combo.setFixedHeight(30)
        cy = datetime.now().year
        for y in range(cy - 3, cy + 2):
            self._yr_combo.addItem(str(y), y)
        self._yr_combo.setCurrentIndex(3)   # current year
        self._yr_combo.currentIndexChanged.connect(self.refresh)

        # Refresh button
        rfsh_btn = QPushButton('↺')
        rfsh_btn.setFixedSize(30, 30)
        rfsh_btn.setToolTip('Actualiser maintenant')
        rfsh_btn.setStyleSheet(
            f'QPushButton{{background:{SUCCESS_LIGHT};color:{SUCCESS};border:none;'
            f'border-radius:8px;font-size:15px;font-weight:700;}}'
            f'QPushButton:hover{{background:{SUCCESS};color:white;}}'
        )
        rfsh_btn.clicked.connect(self.refresh)

        self._ts_lbl = QLabel('')
        self._ts_lbl.setStyleSheet(
            'color:#9CA3AF;font-size:9px;background:transparent;'
        )

        for w in [_lbl_yr, self._yr_combo, rfsh_btn, self._ts_lbl]:
            hdr.addWidget(w)

        card_lay.addLayout(hdr)

        # ── Summary stats strip ───────────────────────────────────────────────
        self._stats_row = QHBoxLayout()
        self._stats_row.setSpacing(12)
        self._stats_row.setContentsMargins(4, 0, 4, 0)
        # Placeholders — filled in after first draw
        self._stat_widgets = []
        for _ in range(4):
            lbl = QLabel('—')
            lbl.setStyleSheet(
                f'color:{TEXT_SUB};font-size:10px;background:transparent;'
            )
            self._stats_row.addWidget(lbl)
            self._stat_widgets.append(lbl)
        self._stats_row.addStretch()
        card_lay.addLayout(self._stats_row)

        # ── Chart area ────────────────────────────────────────────────────────
        self._chart_lay = QVBoxLayout()
        self._chart_lay.setContentsMargins(0, 0, 0, 0)
        self._chart_lay.setSpacing(0)

        self._placeholder = QLabel('Chargement du graphique…')
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            'color:#D1D5DB;font-size:13px;background:transparent;padding:40px;'
        )
        self._chart_lay.addWidget(self._placeholder)
        card_lay.addLayout(self._chart_lay, 1)

        outer.addWidget(self._card)

    # ── Stat strip helpers ────────────────────────────────────────────────────

    def _update_stats(self, year, prf, is_cy, cm):
        realized = [v for i, v in enumerate(prf) if not (is_cy and i > cm)]
        if not realized:
            return
        ytd       = sum(realized)
        best_i    = prf.index(max(prf))
        worst_i   = prf.index(min(prf))
        avg       = sum(realized) / len(realized) if realized else 0

        def _f(v):
            sign = '+' if v > 0 else ''
            if abs(v) >= 1_000_000: return f'{sign}{v/1_000_000:.2f}M MAD'
            if abs(v) >= 1_000:     return f'{sign}{v/1_000:.1f}k MAD'
            return f'{sign}{v:.0f} MAD'

        stats = [
            (f'Cumul {year} : {_f(ytd)}',
             SUCCESS if ytd >= 0 else DANGER),
            (f'Meilleur mois : {_SHORT_CAL[best_i]}  {_f(max(prf))}',
             SUCCESS),
            (f'Pire mois : {_SHORT_CAL[worst_i]}  {_f(min(prf))}',
             DANGER),
            (f'Moyenne / mois : {_f(avg)}',
             TEXT_SUB),
        ]
        for lbl, (text, color) in zip(self._stat_widgets, stats):
            lbl.setText(text)
            lbl.setStyleSheet(
                f'color:{color};font-size:10px;font-weight:600;background:transparent;'
            )

    # ── Data computation ──────────────────────────────────────────────────────

    def _compute(self, year: int):
        """
        Returns (rev, exp, sal, prf) — 12-element lists indexed 0=Jan … 11=Dec.
        Two-layer fallback for each source:
          1. payment_date / paid_date  (real recorded date)
          2. Payment.year + Payment.month name mapped to calendar month
        Insurance is always excluded from revenue.
        """
        rev = [0.0] * 12
        exp = [0.0] * 12
        sal = [0.0] * 12

        # Revenue: monthly + transport payments only
        for p in self.session.query(Payment).filter(
            Payment.payment_type.in_(['monthly', 'transport'])
        ).all():
            try:
                if p.payment_date and p.payment_date.year == year:
                    rev[p.payment_date.month - 1] += p.amount or 0
                elif (p.year == year) and p.month:
                    cal = _SCHOOL_CAL.get(p.month, 0)
                    if cal: rev[cal - 1] += p.amount or 0
            except Exception:
                pass

        # Expenses
        for ep in self.session.query(ExpensePayment).filter_by(year=year).all():
            try:
                cal = _SCHOOL_CAL.get(ep.month or '', 0)
                if cal: exp[cal - 1] += ep.amount or 0
            except Exception:
                pass

        # Salaries — null-safe paid check
        for s in self.session.query(Salary).all():
            try:
                if not getattr(s, 'paid', True):
                    continue
                amt = s.net_salary or getattr(s, 'total', 0) or 0
                if s.paid_date and s.paid_date.year == year:
                    sal[s.paid_date.month - 1] += amt
                elif (s.year == year) and s.month:
                    cal = _SCHOOL_CAL.get(s.month, 0)
                    if cal: sal[cal - 1] += amt
            except Exception:
                pass

        prf = [rev[i] - exp[i] - sal[i] for i in range(12)]
        return rev, exp, sal, prf

    # ── Refresh entry points ──────────────────────────────────────────────────

    def refresh(self):
        """Full refresh: expire session, clear cache for this year, redraw."""
        self.session.expire_all()
        year = self._yr_combo.currentData() or datetime.now().year
        self._data.pop(year, None)   # invalidate cache
        self._draw_year(year)

    def _silent_refresh(self):
        """Timer-triggered: expire + redraw without clearing cache indicator."""
        self.session.expire_all()
        year = self._yr_combo.currentData() or datetime.now().year
        self._data.pop(year, None)
        self._draw_year(year)

    def _draw_year(self, year: int):
        if year not in self._data:
            try:
                self._data[year] = self._compute(year)
            except Exception:
                import traceback; traceback.print_exc()
                return
        rev, exp, sal, prf = self._data[year]
        self._draw(year, rev, exp, sal, prf)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self, year, rev, exp, sal, prf):
        # Remove old canvas
        if self._canvas:
            self._canvas.mpl_disconnect(self._cid) if hasattr(self, '_cid') else None
            self._canvas.setParent(None)
            self._canvas = None
        if self._placeholder:
            self._placeholder.setParent(None)
            self._placeholder = None
        for i in reversed(range(self._chart_lay.count())):
            w = self._chart_lay.itemAt(i).widget()
            if w: w.setParent(None)

        now    = datetime.now()
        cm     = now.month - 1        # 0-based current month index
        cy     = now.year
        is_cy  = (year == cy)

        # ── Figure ────────────────────────────────────────────────────────────
        fig = Figure(figsize=(13, 3.5), facecolor='white')
        fig.subplots_adjust(left=0.055, right=0.975, top=0.84, bottom=0.14)
        ax = fig.add_subplot(111)
        ax.set_facecolor('white')

        xs = list(range(12))
        W  = 0.62

        # ── Bar colours ───────────────────────────────────────────────────────
        face_c, edge_c, lw_v, alpha_v = [], [], [], []
        for i, v in enumerate(prf):
            is_cur  = is_cy and i == cm
            is_fut  = is_cy and i > cm
            is_zero = (rev[i] == 0 and exp[i] == 0 and sal[i] == 0)

            if is_fut and is_zero:
                fc, ec = '#F3F4F6', '#E5E7EB'
            elif v >= 0:
                fc, ec = '#10B981', '#059669'
            else:
                fc, ec = '#EF4444', '#DC2626'

            face_c.append(fc)
            edge_c.append('#4F46E5' if is_cur else ec)
            lw_v.append(2.4 if is_cur else 0.6)
            alpha_v.append(0.35 if (is_fut and is_zero) else 1.0)

        # ── Draw bars ─────────────────────────────────────────────────────────
        self._bars = ax.bar(
            xs, prf,
            color=face_c, edgecolor=edge_c, linewidth=lw_v,
            width=W, zorder=3
        )
        for bar, alph in zip(self._bars, alpha_v):
            bar.set_alpha(alph)

        # ── Zero baseline ─────────────────────────────────────────────────────
        ax.axhline(0, color='#CBD5E1', linewidth=0.8, zorder=2)

        # ── Cumulative line (up to current month only) ────────────────────────
        cx_pts, cy_pts, run = [], [], 0.0
        for i, v in enumerate(prf):
            if is_cy and i > cm:
                break
            run += v
            cx_pts.append(i)
            cy_pts.append(run)

        if len(cx_pts) > 1:
            ax.plot(
                cx_pts, cy_pts,
                color='#4F46E5', linewidth=2.0, linestyle='--',
                zorder=4, alpha=0.85,
                marker='o', markersize=3.0,
                markerfacecolor='white', markeredgewidth=1.4,
                markeredgecolor='#4F46E5',
                label='Cumul annuel',
            )

        # ── Value labels ──────────────────────────────────────────────────────
        mx = max((abs(v) for v in prf), default=1) or 1
        for i, (bar, v) in enumerate(zip(self._bars, prf)):
            if is_cy and i > cm and abs(v) < 1:
                continue
            if abs(v) < mx * 0.02:   # skip tiny bars — avoid clutter
                continue
            txt = (f'{v/1_000_000:.2f}M' if abs(v) >= 1_000_000
                   else f'{v/1_000:.1f}k' if abs(v) >= 1_000
                   else f'{v:.0f}')
            y_off = 4 if v >= 0 else -11
            ax.annotate(
                txt,
                xy=(bar.get_x() + bar.get_width() / 2, v),
                xytext=(0, y_off),
                textcoords='offset points',
                ha='center', fontsize=6.5, fontweight='600',
                color='#059669' if v >= 0 else '#DC2626',
                zorder=5,
            )

        # ── Current month marker ──────────────────────────────────────────────
        if is_cy and 0 <= cm < 12:
            ax.annotate(
                '▼  Maintenant',
                xy=(cm, max(prf[cm], 0)),
                xytext=(0, 12),
                textcoords='offset points',
                ha='center', fontsize=7, fontweight='700',
                color='#4F46E5',
            )

        # ── X axis ────────────────────────────────────────────────────────────
        ax.set_xticks(xs)
        ax.set_xticklabels(_SHORT_CAL, fontsize=8.5)
        for i, tick in enumerate(ax.get_xticklabels()):
            is_cur = is_cy and i == cm
            tick.set_color('#4F46E5' if is_cur else '#6B7280')
            tick.set_fontweight('bold' if is_cur else 'normal')
            tick.set_fontsize(9 if is_cur else 8)

        # ── Y axis ────────────────────────────────────────────────────────────
        ax.yaxis.set_tick_params(labelcolor='#9CA3AF', labelsize=8)
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(
                lambda v, _: (
                    f'{v/1_000_000:.1f}M' if abs(v) >= 1_000_000
                    else f'{v/1_000:.0f}k' if abs(v) >= 1_000
                    else f'{v:.0f}'
                )
            )
        )
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.yaxis.grid(True, color='#F3F4F8', linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)

        # ── Figure title (right-aligned cumulative) ───────────────────────────
        realized = [v for i, v in enumerate(prf) if not (is_cy and i > cm)]
        ytd = sum(realized)
        t_col  = '#059669' if ytd >= 0 else '#DC2626'
        t_sign = '+' if ytd > 0 else ''
        if abs(ytd) >= 1_000_000:
            t_lbl = f'{t_sign}{ytd/1_000_000:.2f}M MAD'
        elif abs(ytd) >= 1_000:
            t_lbl = f'{t_sign}{ytd/1_000:.1f}k MAD'
        else:
            t_lbl = f'{t_sign}{ytd:.0f} MAD'

        ax.set_title(
            f'Bénéfice {year}  ·  YTD : {t_lbl}',
            fontsize=9.5, fontweight='800',
            color=t_col, pad=6, loc='right',
        )

        # ── Legend ────────────────────────────────────────────────────────────
        legend_handles = [
            Patch(facecolor='#10B981', edgecolor='#059669',
                  label='Bénéfice positif'),
            Patch(facecolor='#EF4444', edgecolor='#DC2626',
                  label='Bénéfice négatif'),
            Line2D([0], [0], color='#4F46E5', linewidth=1.8,
                   linestyle='--', marker='o', markersize=3,
                   label='Cumul annuel'),
            Patch(facecolor='#F3F4F6', edgecolor='#E5E7EB',
                  label='Données non disponibles'),
        ]
        ax.legend(
            handles=legend_handles,
            fontsize=7.5, frameon=False,
            loc='upper left', ncol=4,
        )

        # ── Hover tooltip ─────────────────────────────────────────────────────
        annot = ax.annotate(
            '', xy=(0, 0),
            xytext=(12, 12), textcoords='offset points',
            bbox=dict(boxstyle='round,pad=0.5', fc='white',
                      ec='#E5E7EB', lw=1.0, alpha=0.95),
            fontsize=8,
            arrowprops=dict(arrowstyle='->', color='#9CA3AF', lw=0.8),
        )
        annot.set_visible(False)

        def _on_hover(event):
            if event.inaxes != ax:
                annot.set_visible(False)
                fig.canvas.draw_idle()
                return
            for i, bar in enumerate(self._bars):
                if bar.contains(event)[0]:
                    r_str = _fmt_mad_signed(rev[i])
                    e_str = _fmt_mad_signed(-exp[i])
                    s_str = _fmt_mad_signed(-sal[i])
                    p_str = _fmt_mad_signed(prf[i])
                    annot.set_text(
                        f'{_SHORT_CAL[i]}\n'
                        f'Rev  {r_str}\n'
                        f'Dep  {e_str}\n'
                        f'Sal  {s_str}\n'
                        f'───────\n'
                        f'= {p_str}'
                    )
                    annot.xy = (
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() if prf[i] >= 0 else 0,
                    )
                    annot.set_visible(True)
                    fig.canvas.draw_idle()
                    return
            annot.set_visible(False)
            fig.canvas.draw_idle()

        self._fig = fig
        canvas = FigureCanvas(fig)
        canvas.setStyleSheet('background:white;border-radius:8px;')
        canvas.setMinimumHeight(240)
        self._cid = canvas.mpl_connect('motion_notify_event', _on_hover)
        self._canvas = canvas
        self._chart_lay.addWidget(canvas)

        # Update stats strip
        self._update_stats(year, prf, is_cy, cm)

        # Timestamp
        self._ts_lbl.setText(f'↻ {now.strftime("%H:%M:%S")}')


def _fmt_mad_signed(v: float) -> str:
    sign = '+' if v > 0 else ''
    if abs(v) >= 1_000_000: return f'{sign}{v/1_000_000:.2f}M'
    if abs(v) >= 1_000:     return f'{sign}{v/1_000:.1f}k'
    return f'{sign}{v:.0f}'

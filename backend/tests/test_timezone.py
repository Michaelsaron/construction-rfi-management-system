"""BR-09 notice period is measured in SITE time, not the server (container) clock."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from app.models import Rfi
from app.services.workflow import compute_notice, site_now


def test_site_now_is_addis_ababa_wall_clock():
    utc = datetime.now(timezone.utc).replace(tzinfo=None)
    diff = (site_now() - utc).total_seconds() / 3600
    assert round(diff) == 3   # Africa/Addis_Ababa = UTC+3, no DST


def test_short_notice_uses_site_time():
    now_site = site_now()
    r = Rfi(inspection_date=(now_site + timedelta(hours=22)).date(), inspection_time=(now_site + timedelta(hours=22)).strftime('%H:%M'))
    compute_notice(r, now_site, 24)
    assert r.short_notice is True and 21.9 <= r.notice_hours <= 22.1
    # Using the UTC clock instead would over-state the notice by 3 h (25 h -> not flagged): the bug this guards against
    r2 = Rfi(inspection_date=r.inspection_date, inspection_time=r.inspection_time)
    compute_notice(r2, datetime.now(timezone.utc).replace(tzinfo=None), 24)
    assert r2.notice_hours > 24

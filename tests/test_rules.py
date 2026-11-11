from datetime import date
from dashboard.rules import score_email, what_to_wear, is_deadline, free_gaps, find_deadlines


def h(time, feels, rain, wind):
    return {"time": time, "temp": feels, "feels": feels, "rain": rain, "wind": wind, "code": 3}

def allday(title, day):
    return {"title": title, "start": day, "end": day, "all_day": True, "calendar": "c", "location": ""}

def timed_on(day, title, s="10:00", e="11:00"):
    return {"title": title, "start": f"{day}T{s}:00+00:00", "end": f"{day}T{e}:00+00:00",
            "all_day": False, "calendar": "c", "location": ""}

def timed(s, e):
    return timed_on("2026-11-11", "x", s, e)


def test_uni_unread_deadline_scores_high(CFG):
    s, r = score_email("Tutor <a.b@kcl.ac.uk>", "Coursework deadline Friday", "", True, False, CFG)
    assert s == 3 + 2 + 2 and "uni sender" in r

def test_newsletter_penalised(CFG):
    s, r = score_email("Shop <noreply@shop.com>", "Payment offer", "", True, True, CFG)
    assert s < 3 and "newsletter" in r

def test_subject_keyword_cap(CFG):
    s, _ = score_email("x@y.com", "urgent payment overdue invoice", "", False, False, CFG)
    assert s == 4

def test_preview_keyword_cap(CFG):
    s, _ = score_email("x@y.com", "hi", "urgent payment exam", False, False, CFG)
    assert s == 2

def test_wear_cold_rain():
    hourly = [h("2026-11-11T%02d:00" % i, 3, 60 if i >= 15 else 0, 10) for i in range(24)]
    assert what_to_wear(hourly, "2026-11-11")["text"] == "Heavy coat, layers + umbrella (rain from 15:00)"

def test_wear_warm_windy():
    hourly = [h("2026-11-11T%02d:00" % i, 20, 0, 35) for i in range(24)]
    assert what_to_wear(hourly, "2026-11-11")["text"] == "T-shirt weather + windproof"

def test_wear_no_data():
    assert what_to_wear([], "2026-11-11") is None

def test_is_deadline(CFG):
    assert is_deadline("ML coursework DUE", CFG) and is_deadline("Hand-in essay", CFG)
    assert not is_deadline("Football training", CFG)

def test_free_gaps_ignores_all_day_and_short_gaps():
    ev = [allday("Holiday", "2026-11-11"), timed("10:00", "11:00"), timed("11:30", "12:00"), timed("15:00", "16:00")]
    gaps = free_gaps(ev, "2026-11-11", "Europe/London")
    assert [(g["start"][11:16], g["end"][11:16]) for g in gaps] == [("08:00", "10:00"), ("12:00", "15:00"), ("16:00", "22:00")]

def test_free_gaps_overlapping_events_merge():
    gaps = free_gaps([timed("09:00", "13:00"), timed("10:00", "12:00")], "2026-11-11", "Europe/London")
    assert [(g["start"][11:16], g["end"][11:16]) for g in gaps] == [("08:00", "09:00"), ("13:00", "22:00")]

def test_free_gaps_empty_day():
    assert free_gaps([], "2026-11-11", "Europe/London")[0]["minutes"] == 840

def test_find_deadlines_from_events_sorted(CFG):
    d = find_deadlines([timed_on("2026-11-14", "Essay due"), timed_on("2026-11-12", "Exam"), timed_on("2026-11-12", "Gym")],
                       [], date(2026, 11, 11), CFG)
    assert [x["title"] for x in d] == ["Exam", "Essay due"] and d[0]["days_left"] == 1 and d[0]["source"] == "calendar"

def test_find_deadlines_from_email_date(CFG):
    em = [{"subject": "Coursework due 20th Nov", "preview": "", "score": 7, "from": "t@kcl.ac.uk"},
          {"subject": "Due 21 Nov", "preview": "", "score": 3, "from": "x"}]
    d = find_deadlines([], em, date(2026, 11, 11), CFG)
    assert len(d) == 1 and d[0]["due"] == "2026-11-20" and d[0]["source"] == "email" and d[0]["days_left"] == 9

def test_find_deadlines_email_date_rolls_year(CFG):
    em = [{"subject": "Exam on 5 Jan", "preview": "", "score": 7, "from": "t"}]
    assert find_deadlines([], em, date(2026, 12, 20), CFG)[0]["due"] == "2027-01-05"

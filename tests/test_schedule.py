import pytest

from apod_wallpaper import schedule


def test_parse_time():
    assert schedule._parse_time("09:00") == (9, 0)
    assert schedule._parse_time("23:59") == (23, 59)
    for bad in ("24:00", "9", "aa:bb", "12:60"):
        with pytest.raises(schedule.ScheduleError):
            schedule._parse_time(bad)


def test_systemd_quote():
    assert schedule._systemd_quote('/a b/c"d%') == '"/a b/c\\"d%%"'


def test_windows_task_xml_escapes_and_quotes(monkeypatch):
    monkeypatch.setattr(schedule, "command", lambda: ["C:\\A & B\\app.exe", "C:\\x y\\l.py", "--scheduled"])
    xml = schedule._win_xml(7, 30)
    assert "<StartBoundary>2025-01-01T07:30:00</StartBoundary>" in xml
    assert "<Command>C:\\A &amp; B\\app.exe</Command>" in xml
    assert '<Arguments>"C:\\x y\\l.py" --scheduled</Arguments>' in xml

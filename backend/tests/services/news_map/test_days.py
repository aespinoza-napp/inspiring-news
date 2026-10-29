from datetime import date

from src.services.news_map.days import MADRID, UTC, publication_day, zone_of


def test_the_day_is_madrids_in_summer_and_in_winter():
    """
    22:30 UTC is 00:30 the next day in Madrid in summer time and 23:30
    the same day in winter time (since 25 Oct 2026).
    """

    assert publication_day("2026-07-28T22:30:00+00:00") == date(2026, 7, 29)
    assert publication_day("2026-10-28T22:30:00+00:00") == date(2026, 10, 28)
    assert publication_day("2026-10-28T22:30:00Z") == date(2026, 10, 28)


def test_a_naive_time_is_in_its_sources_zone():

    # 23:00 in New York is 05:00 the next day in Madrid (winter, both sides).
    assert publication_day("2026-11-10T23:00:00", source_zone=zone_of("US")) == date(2026, 11, 11)
    assert publication_day("2026-11-10T23:00:00", source_zone=zone_of("ES")) == date(2026, 11, 10)


def test_a_country_without_a_zone_is_utc_and_spain_is_madrid():

    assert zone_of("INT") is UTC
    assert zone_of(None) is UTC
    assert zone_of("es") is MADRID


def test_without_a_publication_time_the_check_time_decides():

    assert publication_day(None, "2026-10-29T10:00:00+00:00") == date(2026, 10, 29)
    assert publication_day("not a date", None) is None
    assert publication_day(None, None) is None

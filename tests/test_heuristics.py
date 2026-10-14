from pathlib import Path
from src.metadata.heuristics import parse_path_hierarchy, parse_filename, extract_year_from_album
from src.config import sanitize_component


def test_clean_windows_component():
    assert sanitize_component("AC/DC") == "AC_DC"
    assert sanitize_component("Track: 01 *special*?") == "Track_ 01 _special__"
    assert sanitize_component("CON") == "_CON"
    assert sanitize_component("   ") == "Unknown"


def test_extract_year_from_album():
    alb, yr = extract_year_from_album("1973 - The Dark Side of the Moon")
    assert alb == "The Dark Side of the Moon"
    assert yr == 1973

    alb2, yr2 = extract_year_from_album("Abbey Road (1969)")
    assert alb2 == "Abbey Road"
    assert yr2 == 1969


def test_parse_filename():
    r1 = parse_filename("01 - Speak to Me")
    assert r1["track_number"] == 1
    assert r1["title"] == "Speak to Me"

    r2 = parse_filename("05. Money")
    assert r2["track_number"] == 5
    assert r2["title"] == "Money"

    r3 = parse_filename("Queen - Bohemian Rhapsody")
    assert r3["artist"] == "Queen"
    assert r3["title"] == "Bohemian Rhapsody"


def test_parse_path_hierarchy_three_levels():
    source_dir = Path("C:/MusicSource")
    file_path = source_dir / "Rock" / "Pink Floyd" / "1973 - Dark Side" / "01 - Speak to Me.mp3"

    info = parse_path_hierarchy(file_path, source_dir)
    assert info["style"] == "Rock"
    assert info["artist"] == "Pink Floyd"
    assert info["album"] == "Dark Side"
    assert info["year"] == 1973
    assert info["track_number"] == 1
    assert info["title"] == "Speak to Me"


def test_parse_path_hierarchy_with_disc():
    source_dir = Path("C:/MusicSource")
    file_path = source_dir / "Rock" / "The Beatles" / "White Album" / "CD 2" / "01 - Birthday.mp3"

    info = parse_path_hierarchy(file_path, source_dir)
    assert info["artist"] == "The Beatles"
    assert info["album"] == "White Album"
    assert info["disc_number"] == 2
    assert info["track_number"] == 1

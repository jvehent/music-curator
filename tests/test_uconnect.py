import io
import tempfile
from pathlib import Path
from PIL import Image

import mutagen
from mutagen.id3 import ID3, APIC, Encoding

from src.config import CuratorConfig, sanitize_uconnect_string
from src.metadata.models import TrackMetadata
from src.metadata.writer import update_audio_tags
from src.organizer.planner import OrganizationPlanner


def test_rule_3_uconnect_string_sanitization():
    # Accented characters transliterated to ASCII
    assert sanitize_uconnect_string("Édition Spéciale") == "Edition Speciale"
    assert sanitize_uconnect_string("Niño / Señor") == "Nino Senor"
    assert sanitize_uconnect_string("Björk - Álbum") == "Bjork - Album"

    # Avoid special characters
    assert sanitize_uconnect_string("Track: ? * < > | \"") == "Track"

    # Length strictly under 32 chars
    long_name = "Supercalifragilisticexpialidocious Deluxe Edition"
    cleaned = sanitize_uconnect_string(long_name, max_length=32)
    assert len(cleaned) <= 32
    assert cleaned == "Supercalifragilisticexpialidocio"


def test_rule_1_and_3_planner_max_depth_and_32_char_filename():
    config = CuratorConfig(
        destination_dir=Path("C:/UconnectMusic"),
        uconnect_mode=True,
        max_component_length=32,
    )
    planner = OrganizationPlanner(config)

    # Multi-disc track with long title and accents
    track = TrackMetadata(
        file_path=Path("C:/Disorganized/Electro/Daft Punk/Alive 2007/Disc 2/05 - Électro Jam Extraordinaire.mp3"),
        format=".mp3",
        artist="Daft Punk Deluxe Edition 2007 Remaster",
        album="Alive 2007 Very Long Album Title That Exceeds Limit",
        title="Électro Jam Extraordinaire Extended Version",
        track_number=5,
        disc_number=2,
        confidence="high",
    )

    plan = planner.create_plan([track])
    assert len(plan) == 1
    item = plan[0]

    # Verify 2 folder depth
    rel_path = item.target_path.relative_to(config.destination_dir)
    assert len(rel_path.parts) == 3  # [Artist, Album, Filename]

    # Verify length limits
    assert len(item.target_artist_dir) <= 32
    assert len(item.target_album_dir) <= 32
    assert len(item.target_filename) <= 32

    # Verify no accented characters in path
    assert "É" not in str(item.target_path)
    assert "é" not in str(item.target_path)

    # Verify disc prefix in filename without creating subfolder
    assert item.target_filename.startswith("2-05 - ")
    assert item.target_filename.endswith(".mp3")


def test_rule_2_and_4_id3v23_and_artwork_strip():
    with tempfile.TemporaryDirectory() as td:
        target_mp3 = Path(td) / "test_track.mp3"

        # Create base MP3 with large dummy cover art (1000x1000)
        img = Image.new("RGB", (1000, 1000), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        raw_art = buf.getvalue()

        id3 = ID3()
        id3.add(APIC(encoding=Encoding.LATIN1, mime="image/jpeg", type=3, desc="Cover", data=raw_art))
        id3.save(target_mp3, v2_version=4)  # Initially v2.4

        # Track metadata with accented title
        meta = TrackMetadata(
            file_path=target_mp3,
            format=".mp3",
            artist="Beyoncé",
            album="Renaissance (Édition)",
            title="Cuff It (Remix)",
            track_number=4,
        )

        # Update with Uconnect rules (ID3v2.3, strip artwork)
        success = update_audio_tags(
            target_file=target_mp3,
            meta=meta,
            id3_version="2.3",
            artwork_action="strip",
            uconnect_mode=True,
        )
        assert success is True

        # Re-read and verify ID3v2.3
        read_tags = ID3(target_mp3)
        assert read_tags.version == (2, 3, 0)  # Standard ID3v2.3!

        # Verify populated fields
        assert str(read_tags["TPE1"]) == "Beyonce"  # Transliterated
        assert str(read_tags["TALB"]) == "Renaissance (Edition)"
        assert str(read_tags["TIT2"]) == "Cuff It (Remix)"
        assert str(read_tags["TRCK"]) == "4"

        # Verify artwork was stripped
        assert len(read_tags.getall("APIC")) == 0


def test_rule_4_artwork_resize_to_500():
    with tempfile.TemporaryDirectory() as td:
        target_mp3 = Path(td) / "test_resize.mp3"

        # 1200x1200 image
        img = Image.new("RGB", (1200, 1200), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")

        id3 = ID3()
        id3.add(APIC(encoding=Encoding.LATIN1, mime="image/jpeg", type=3, desc="Cover", data=buf.getvalue()))
        id3.save(target_mp3, v2_version=3)

        meta = TrackMetadata(
            file_path=target_mp3,
            format=".mp3",
            artist="Artist",
            album="Album",
            title="Title",
            track_number=1,
        )

        update_audio_tags(
            target_file=target_mp3,
            meta=meta,
            artwork_action="resize_500",
            uconnect_mode=True,
        )

        read_tags = ID3(target_mp3)
        apics = read_tags.getall("APIC")
        assert len(apics) == 1
        resized_img = Image.open(io.BytesIO(apics[0].data))
        assert resized_img.width <= 500
        assert resized_img.height <= 500

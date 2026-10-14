from pathlib import Path
from src.config import CuratorConfig
from src.metadata.models import TrackMetadata
from src.organizer.planner import OrganizationPlanner


def test_planner_basic():
    config = CuratorConfig(destination_dir=Path("C:/CleanMusic"))
    planner = OrganizationPlanner(config)

    t1 = TrackMetadata(
        file_path=Path("C:/Disorganized/Rock/Queen/A Night at the Opera/04 - You're My Best Friend.mp3"),
        format=".mp3",
        artist="Queen",
        album="A Night at the Opera",
        title="You're My Best Friend",
        track_number=4,
        confidence="high",
    )

    plan = planner.create_plan([t1])
    assert len(plan) == 1
    item = plan[0]

    assert item.target_artist_dir == "Queen"
    assert item.target_album_dir == "A Night at the Opera"
    assert item.target_filename == "04 - You're My Best Friend.mp3"
    assert item.status == "ready"


def test_planner_collision_handling():
    config = CuratorConfig(destination_dir=Path("C:/CleanMusic"), conflict_strategy="suffix")
    planner = OrganizationPlanner(config)

    t1 = TrackMetadata(
        file_path=Path("C:/Dir1/Song.mp3"),
        format=".mp3",
        artist="Artist",
        album="Album",
        title="Song",
        track_number=1,
    )
    t2 = TrackMetadata(
        file_path=Path("C:/Dir2/Song.mp3"),
        format=".mp3",
        artist="Artist",
        album="Album",
        title="Song",
        track_number=1,
    )

    plan = planner.create_plan([t1, t2])
    assert len(plan) == 2
    assert plan[0].target_filename == "01 - Song.mp3"
    assert plan[1].target_filename == "01 - Song (1).mp3"
    assert plan[1].has_conflict is True

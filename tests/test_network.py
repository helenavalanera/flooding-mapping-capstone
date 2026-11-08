import osmium
import pytest

from flooding_mapping.network import SPLIT_ID_OFFSET, _runs, read_segments, write_blocked_pbf

CRS = "EPSG:31982"


@pytest.fixture
def pbf(tmp_path):
    """One highway way 1-2-3-4-5 and one non-highway way."""
    path = tmp_path / "toy.osm.pbf"
    with osmium.SimpleWriter(str(path)) as writer:
        for i in range(1, 6):
            writer.add_node(osmium.osm.mutable.Node(id=i, location=(-51.2 + i * 0.001, -30.0)))
        writer.add_way(osmium.osm.mutable.Way(id=10, nodes=[1, 2, 3, 4, 5],
                                              tags={"highway": "residential", "name": "Rua X"}))
        writer.add_way(osmium.osm.mutable.Way(id=11, nodes=[1, 2], tags={"building": "yes"}))
    return path


def ways(path):
    return {w.id: ([n.ref for n in w.nodes], dict(w.tags))
            for w in osmium.FileProcessor(str(path), osmium.osm.WAY)}


def test_runs_split_free_and_blocked_pairs():
    free, cut = _runs([1, 2, 3, 4, 5], {(2, 3), (3, 4)})
    assert free == [[1, 2], [4, 5]]
    assert cut == [[2, 3, 4]]
    assert _runs([1, 2, 3], set()) == ([[1, 2, 3]], [])


def test_segments_have_unique_ids_and_lengths(pbf):
    segments = read_segments(pbf, CRS)
    assert segments["segment_id"].tolist() == ["10:1:2", "10:2:3", "10:3:4", "10:4:5"]
    assert (segments["length_m"] > 90).all()
    assert segments["walk"].all() and segments["drive"].all()


def test_blocked_pbf_removes_only_blocked_segments(pbf, tmp_path):
    out = tmp_path / "blocked.osm.pbf"
    stats = write_blocked_pbf(pbf, out, {"10:2:3", "10:3:4"}, "all")
    assert stats == {"ways_split": 1, "segments_blocked": 2}
    result = ways(out)
    assert result[10][0] == [1, 2]                      # original id keeps the first run
    assert result[SPLIT_ID_OFFSET][0] == [4, 5]         # second free run gets a new id
    assert result[11][0] == [1, 2]                      # untouched way preserved
    assert set(ways(pbf)[10][0]) == {1, 2, 3, 4, 5}     # source unchanged
    remaining = set(read_segments(out, CRS)["segment_id"])
    assert remaining == {"10:1:2", f"{SPLIT_ID_OFFSET}:4:5"}


def test_driving_only_blocking_keeps_segments_for_walking(pbf, tmp_path):
    out = tmp_path / "car.osm.pbf"
    write_blocked_pbf(pbf, out, {"10:2:3"}, "driving")
    tagged = [tags for _, tags in ways(out).values() if tags.get("motor_vehicle") == "no"]
    assert len(tagged) == 1 and tagged[0]["highway"] == "residential"
    segments = read_segments(out, CRS)
    assert len(segments) == 4
    assert segments["walk"].all()
    assert segments["drive"].sum() == 3

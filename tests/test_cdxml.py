import xml.etree.ElementTree as ET
from pathlib import Path

import ase
import numpy as np
import pytest

import aiidalab_widgets_base as awb
from aiidalab_widgets_base.cdxml import (
    _bounded_faces,
    _has_bond_crossings,
    _signed_area,
)

DATA_DIR = Path(__file__).parent / "data" / "cdxml"


@pytest.fixture
def file_upload_change():
    def create_change(filename, content):
        return {
            "new": (
                {
                    "name": filename,
                    "content": content.encode("utf-8"),
                },
            )
        }

    return create_change


def _explicit_edges(content):
    root = ET.fromstring(content)
    atom_ids = [node.get("id") for node in root.iter("n") if "p" in node.attrib]
    atom_index = {atom_id: index for index, atom_id in enumerate(atom_ids)}
    return [
        (atom_index[bond.get("B")], atom_index[bond.get("E")])
        for bond in root.iter("b")
        if bond.get("B") in atom_index and bond.get("E") in atom_index
    ]


def _sp2_angle_error(positions, edges):
    adjacency = [[] for _ in positions]
    for first, second in edges:
        adjacency[first].append(second)
        adjacency[second].append(first)

    errors = []
    for center, neighbors in enumerate(adjacency):
        if len(neighbors) not in (2, 3):
            continue
        for first_index in range(len(neighbors)):
            for second_index in range(first_index + 1, len(neighbors)):
                first = positions[neighbors[first_index]] - positions[center]
                second = positions[neighbors[second_index]] - positions[center]
                cosine = np.dot(first, second) / (
                    np.linalg.norm(first) * np.linalg.norm(second)
                )
                errors.append((cosine + 0.5) ** 2)
    return float(np.sqrt(np.mean(errors)))


def test_structure_upload_widget(file_upload_change):
    widget = awb.CdxmlUploadWidget()
    assert widget.structure is None

    content = (DATA_DIR / "7AGNR.cdxml").read_text()
    widget._on_file_upload(file_upload_change("7AGNR.cdxml", content))
    widget.create_button.click()

    assert isinstance(widget.structure, ase.Atoms)
    assert widget.structure.get_chemical_formula() == "C14H4"
    assert widget.structure.pbc.tolist() == [True, False, False]
    assert "Ready to create" not in widget.output_message.value

    widget._on_file_upload(file_upload_change("7AGNR.cdxml", content))
    widget.nunits.value = "2"
    widget.create_button.click()
    assert widget.structure.get_chemical_formula() == "C56H22"

    content = (DATA_DIR / "benzene.cdxml").read_text()
    widget._on_file_upload(file_upload_change("benzene.cdxml", content))
    widget.create_button.click()
    assert widget.structure.get_chemical_formula() == "C6H6"
    assert not widget.structure.pbc.any()


def test_planarity_check_rejects_crossing_and_overlapping_bonds():
    crossing_positions = np.array([[0.0, 0.0], [1.0, 1.0], [0.0, 1.0], [1.0, 0.0]])
    overlapping_positions = np.array([[0.0, 0.0], [2.0, 0.0], [0.5, 0.0], [1.5, 0.0]])

    assert _has_bond_crossings(crossing_positions, [(0, 1), (2, 3)])
    assert _has_bond_crossings(overlapping_positions, [(0, 1), (2, 3)])


def test_periodic_crossings_are_independent_of_bracket_order():
    content = (DATA_DIR / "mixed_rings_periodic.cdxml").read_bytes()
    widget = awb.CdxmlUploadWidget()

    crossing_points, _, is_not_periodic = widget.extract_crossing_and_atom_positions(
        content
    )

    assert not is_not_periodic
    assert crossing_points is not None
    assert crossing_points.shape == (2, 3)
    assert np.linalg.norm(crossing_points[1] - crossing_points[0]) == pytest.approx(
        42.75, abs=0.05
    )


def test_cdxml_scaling_uses_explicit_carbon_bonds():
    content = (DATA_DIR / "mixed_rings_periodic.cdxml").read_bytes()
    edges = _explicit_edges(content)
    scaled_root = ET.fromstring(content)
    for node in scaled_root.iter("n"):
        if "p" not in node.attrib:
            continue
        coordinates = [5.0 * float(value) for value in node.attrib["p"].split()]
        node.attrib["p"] = " ".join(str(value) for value in coordinates)

    _, original, _ = awb.CdxmlUploadWidget.cdxml_to_ase_from_string(content)
    _, rescaled, _ = awb.CdxmlUploadWidget.cdxml_to_ase_from_string(
        ET.tostring(scaled_root)
    )
    original_lengths = sorted(
        np.linalg.norm(original.positions[second] - original.positions[first])
        for first, second in edges
    )
    rescaled_lengths = sorted(
        np.linalg.norm(rescaled.positions[second] - rescaled.positions[first])
        for first, second in edges
    )

    assert np.allclose(original_lengths, rescaled_lengths)


def test_geometry_cleanup_preserves_planar_fused_ring_graph():
    content = (DATA_DIR / "mixed_rings_periodic.cdxml").read_bytes()
    edges = _explicit_edges(content)

    _, original, _ = awb.CdxmlUploadWidget.cdxml_to_ase_from_string(content)
    message, cleaned, _ = awb.CdxmlUploadWidget.cdxml_to_ase_from_string(
        content, symmetrize=True
    )

    original_positions = original.positions[:, :2]
    cleaned_positions = cleaned.positions[:, :2]
    lengths = np.array(
        [
            np.linalg.norm(cleaned_positions[second] - cleaned_positions[first])
            for first, second in edges
        ]
    )

    assert "cleanup skipped" not in message
    assert lengths.min() >= 1.35
    assert lengths.max() <= 1.60
    assert not _has_bond_crossings(cleaned_positions, edges)
    assert _sp2_angle_error(cleaned_positions, edges) < _sp2_angle_error(
        original_positions, edges
    )

    faces = _bounded_faces(original_positions, edges)
    for face in faces:
        original_area = _signed_area(original_positions[face])
        cleaned_area = _signed_area(cleaned_positions[face])
        assert original_area * cleaned_area > 0

    pentagon_angle_spreads = []
    for face in faces:
        if len(face) != 5:
            continue
        points = cleaned_positions[face]
        angles = []
        for index in range(5):
            first = points[index - 1] - points[index]
            second = points[(index + 1) % 5] - points[index]
            cosine = np.dot(first, second) / (
                np.linalg.norm(first) * np.linalg.norm(second)
            )
            angles.append(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))
        pentagon_angle_spreads.append(np.std(angles))

    assert pentagon_angle_spreads
    assert max(pentagon_angle_spreads) > 5.0


def test_mixed_ring_widget_flow_with_cleanup(file_upload_change):
    content = (DATA_DIR / "mixed_rings_periodic.cdxml").read_text()
    widget = awb.CdxmlUploadWidget()
    widget.symmetrize_geometry.value = True

    widget._on_file_upload(file_upload_change("mixed_rings_periodic.cdxml", content))
    assert not widget.nunits.disabled
    assert widget.crossing_points is not None
    assert "cleanup skipped" not in widget.output_message.value

    widget.create_button.click()

    assert isinstance(widget.structure, ase.Atoms)
    assert widget.structure.pbc.tolist() == [True, False, False]
    assert "Carbon geometry cleaned globally" in widget.output_message.value
    assert "Ready to create" not in widget.output_message.value

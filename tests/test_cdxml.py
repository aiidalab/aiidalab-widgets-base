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
    normalize,
    rotate_vector,
    rotation_matrix_from_vectors,
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


def _minimal_cdxml(nodes, bonds):
    node_xml = "".join(
        f'<n id="{atom_id}" p="{x} {y}" Element="{element}"{extra}/>'
        for atom_id, element, x, y, extra in nodes
    )
    bond_xml = "".join(
        f'<b id="b{index}" B="{first}" E="{second}" Order="{order}"/>'
        for index, (first, second, order) in enumerate(bonds)
    )
    return f"<CDXML><page>{node_xml}{bond_xml}</page></CDXML>"


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


def test_geometry_transform_helpers():
    x_axis = np.array([1.0, 0.0, 0.0])
    y_axis = np.array([0.0, 1.0, 0.0])
    z_axis = np.array([0.0, 0.0, 1.0])

    assert np.allclose(normalize(3.0 * x_axis), x_axis)
    assert np.allclose(normalize(np.zeros(3)), np.zeros(3))
    assert np.allclose(rotation_matrix_from_vectors(x_axis, x_axis), np.eye(3))
    assert np.allclose(rotation_matrix_from_vectors(x_axis, y_axis) @ x_axis, y_axis)
    assert np.allclose(rotate_vector(x_axis, z_axis, np.pi / 2), y_axis)

    source = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    rotation = rotation_matrix_from_vectors(x_axis, y_axis)
    target = 2.0 * np.dot(source, rotation.T) + np.array([4.0, -3.0, 1.0])
    transformed = awb.CdxmlUploadWidget.transform_points(source, target, source)
    assert np.allclose(transformed, target)

    horizontal = np.array([[0.0, 0.0, 0.0], [2.0, 1.0, 0.0]])
    vertical = np.array([[0.0, -2.0, 0.0], [1.0, 3.0, 0.0]])
    assert np.allclose(
        awb.CdxmlUploadWidget.max_extension_points(horizontal),
        [[-7.5, 0.0, 0.0], [9.5, 0.0, 0.0]],
    )
    assert np.allclose(
        awb.CdxmlUploadWidget.max_extension_points(vertical),
        [[0.0, -9.5, 0.0], [0.0, 10.5, 0.0]],
    )


def test_safe_hydrogenation_handles_bonded_and_isolated_carbons():
    acetylene_skeleton = ase.Atoms("C2", positions=[[0.0, 0.0, 0.0], [1.42, 0.0, 0.0]])
    message, hydrogenated = awb.CdxmlUploadWidget.add_safe_hydrogen_atoms(
        acetylene_skeleton
    )

    assert hydrogenated.get_chemical_formula() == "C2H2"
    assert "[0, 1]" in message
    assert hydrogenated.positions[2, 0] < 0.0
    assert hydrogenated.positions[3, 0] > 1.42

    isolated = ase.Atoms("C", positions=[[0.0, 0.0, 0.0]])
    _, isolated_hydrogenated = awb.CdxmlUploadWidget.add_safe_hydrogen_atoms(isolated)
    assert isolated_hydrogenated.get_chemical_formula() == "CH"
    assert np.allclose(isolated_hydrogenated.positions[1], [0.0, 0.0, 1.1])


def test_widget_reports_missing_and_malformed_cdxml(monkeypatch):
    widget = awb.CdxmlUploadWidget()

    widget._on_file_upload()
    widget.create_button.click()
    assert widget.structure is None
    assert "No CDXML file has been uploaded" in widget.output_message.value

    widget._cdxml_content = b"<CDXML><broken>"
    assert not widget._convert_uploaded_cdxml()
    assert "Unexpected error" in widget.output_message.value

    def reject_cdxml(*args, **kwargs):
        raise ValueError("invalid <bond>")

    monkeypatch.setattr(widget, "cdxml_to_ase_from_string", reject_cdxml)
    assert not widget._convert_uploaded_cdxml()
    assert "invalid &lt;bond&gt;" in widget.output_message.value


def test_geometry_cleanup_and_override_validation():
    unchanged = awb.CdxmlUploadWidget.symmetrize_carbon_network(
        np.array([[0.0, 0.0, 0.0], [1.4, 0.0, 0.0]]),
        ["C", "C"],
        [(0, 1)],
    )
    assert np.allclose(unchanged, [[0.0, 0.0, 0.0], [1.4, 0.0, 0.0]])

    crossing_positions = np.array(
        [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
    )
    with pytest.raises(ValueError, match="geometric crossing"):
        awb.CdxmlUploadWidget.symmetrize_carbon_network(
            crossing_positions,
            ["C"] * 4,
            [(0, 1), (2, 3), (0, 2)],
        )

    content = (DATA_DIR / "benzene.cdxml").read_bytes()
    widget = awb.CdxmlUploadWidget()
    with pytest.raises(ValueError, match="atom count"):
        widget.extract_crossing_and_atom_positions(
            content, atom_positions_override=np.zeros((1, 3))
        )
    with pytest.raises(ValueError, match="must have shape"):
        widget.extract_crossing_and_atom_positions(
            content, atom_positions_override=np.zeros((6, 4))
        )

    boundaries, positions, is_not_periodic = widget.extract_crossing_and_atom_positions(
        content, atom_positions_override=np.zeros((6, 2))
    )
    assert is_not_periodic
    assert positions.shape == (6, 3)
    assert boundaries.shape == (2, 3)


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


@pytest.mark.parametrize(
    ("nodes", "bonds", "formula"),
    [
        (
            [("1", "6", 0, 0, ""), ("2", "6", 1, 0, "")],
            [("1", "2", "1")],
            "C2H6",
        ),
        (
            [("1", "6", 0, 0, ""), ("2", "6", 1, 0, "")],
            [("1", "2", "2")],
            "C2H4",
        ),
        (
            [("1", "6", 0, 0, ' Radical="2"'), ("2", "6", 1, 0, "")],
            [("1", "2", "1")],
            "C2H5",
        ),
        ([("1", "8", 0, 0, "")], [], "H2O"),
        (
            [("1", "6", 0, 0, ""), ("2", "8", 1.4, 0, "")],
            [("1", "2", "1")],
            "CH4O",
        ),
        (
            [
                ("1", "6", -1, 0, ""),
                ("2", "7", 0, 0, ""),
                ("3", "6", 0.5, 0.8, ""),
            ],
            [("1", "2", "1"), ("2", "3", "1")],
            "C2H7N",
        ),
        (
            [("1", "6", 0, 0, ""), ("2", "16", 1.8, 0, "")],
            [("1", "2", "1")],
            "CH4S",
        ),
        (
            [
                ("1", "6", -1, 0, ""),
                ("2", "6", 0, 0, ""),
                ("3", "6", 0.5, 0.8, ""),
            ],
            [("1", "2", "1"), ("2", "3", "1")],
            "C3H8",
        ),
    ],
    ids=[
        "ethane",
        "ethene",
        "ethyl-radical",
        "water",
        "methanol",
        "dimethylamine",
        "methanethiol",
        "propane",
    ],
)
def test_implicit_hydrogen_geometries(nodes, bonds, formula):
    _, _, atoms = awb.CdxmlUploadWidget.cdxml_to_ase_from_string(
        _minimal_cdxml(nodes, bonds)
    )

    assert atoms.get_chemical_formula() == formula
    assert np.isfinite(atoms.positions).all()


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

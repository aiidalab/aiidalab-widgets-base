"""Import molecular and periodic structures from ChemDraw CDXML files."""

from __future__ import annotations

import html
import math
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

import ase
import ipywidgets as ipw
import numpy as np
import traitlets as tr
from ase import Atoms
from ase.data import covalent_radii
from ase.neighborlist import NeighborList
from scipy.optimize import least_squares


# ---------------- Utility functions ----------------
def normalize(v: np.ndarray) -> np.ndarray:
    """Return the normalized version of vector v, or zeros if near-zero norm."""
    v = np.array(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else np.zeros(3)


def rotation_matrix_from_vectors(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Return the rotation matrix that rotates vector a into vector b."""
    a, b = normalize(a), normalize(b)
    v = np.cross(a, b)
    c = np.dot(a, b)
    if np.linalg.norm(v) < 1e-8:
        return np.eye(3)
    vx = np.array(
        [
            [0, -v[2], v[1]],
            [v[2], 0, -v[0]],
            [-v[1], v[0], 0],
        ]
    )
    return np.eye(3) + vx + vx @ vx * ((1 - c) / (np.linalg.norm(v) ** 2))


def rotate_vector(v: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
    """Rotate vector v around given axis by 'angle' radians."""
    axis = normalize(axis)
    v = np.array(v)
    return (
        v * math.cos(angle)
        + np.cross(axis, v) * math.sin(angle)
        + axis * np.dot(axis, v) * (1 - math.cos(angle))
    )


def _signed_area(points: np.ndarray) -> float:
    """Return the signed area of a two-dimensional polygon."""
    x, y = points[:, 0], points[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - y * np.roll(x, -1)))


def _bounded_faces(
    positions: np.ndarray, edges: List[Tuple[int, int]]
) -> List[List[int]]:
    """Find bounded faces in an existing straight-line planar embedding."""
    adjacency = {index: [] for index in range(len(positions))}
    for first, second in edges:
        adjacency[first].append(second)
        adjacency[second].append(first)

    ordered = {}
    for center, neighbors in adjacency.items():
        ordered[center] = sorted(
            neighbors,
            key=lambda neighbor: math.atan2(
                positions[neighbor, 1] - positions[center, 1],
                positions[neighbor, 0] - positions[center, 0],
            ),
        )

    visited = set()
    faces = []
    for first, second in edges:
        for start in ((first, second), (second, first)):
            if start in visited:
                continue
            face = []
            current = start
            while current not in visited:
                visited.add(current)
                left, right = current
                face.append(left)
                neighbors = ordered[right]
                if not neighbors:
                    break
                incoming = neighbors.index(left)
                current = (right, neighbors[(incoming - 1) % len(neighbors)])
                if current == start:
                    break
            if current == start and len(face) >= 3 and len(set(face)) == len(face):
                faces.append(face)

    if not faces:
        return []
    areas = [abs(_signed_area(positions[face])) for face in faces]
    exterior = int(np.argmax(areas))
    return [
        face
        for index, face in enumerate(faces)
        if index != exterior and 3 <= len(face) <= 12
    ]


def _segments_properly_cross(
    first: np.ndarray,
    second: np.ndarray,
    third: np.ndarray,
    fourth: np.ndarray,
    tolerance: float = 1.0e-10,
) -> bool:
    """Return whether two line segments cross away from their endpoints."""

    def orientation(a, b, c):
        first = b - a
        second = c - a
        return float(first[0] * second[1] - first[1] * second[0])

    def lies_on_segment(start, end, point):
        if abs(orientation(start, end, point)) > tolerance:
            return False
        return bool(
            np.all(point >= np.minimum(start, end) - tolerance)
            and np.all(point <= np.maximum(start, end) + tolerance)
        )

    o1 = orientation(first, second, third)
    o2 = orientation(first, second, fourth)
    o3 = orientation(third, fourth, first)
    o4 = orientation(third, fourth, second)
    if o1 * o2 < -tolerance and o3 * o4 < -tolerance:
        return True
    return any(
        (
            lies_on_segment(first, second, third),
            lies_on_segment(first, second, fourth),
            lies_on_segment(third, fourth, first),
            lies_on_segment(third, fourth, second),
        )
    )


def _has_bond_crossings(positions: np.ndarray, edges: List[Tuple[int, int]]) -> bool:
    """Check a straight-line graph embedding for non-adjacent bond crossings."""
    for edge_index, (first, second) in enumerate(edges):
        for third, fourth in edges[edge_index + 1 :]:
            if len({first, second, third, fourth}) < 4:
                continue
            if _segments_properly_cross(
                positions[first], positions[second], positions[third], positions[fourth]
            ):
                return True
    return False


# ---------------- Main Widget ----------------
class CdxmlUploadWidget(ipw.VBox):
    """Widget for uploading CDXML files and converting them into ASE.Atoms structures."""

    structure = tr.Instance(ase.Atoms, allow_none=True)

    def __init__(
        self, title: str = "CDXML", description: str = "Upload CDXML"
    ):
        self.title = title

        # --- File upload widget ---
        self.file_upload = ipw.FileUpload(
            description=description,
            multiple=False,
            layout={"width": "initial"},
            accept=".cdxml",
        )
        self.file_upload.observe(self._on_file_upload, names="value")

        # --- Additional widgets ---
        self.nunits = ipw.Text(description="N units", value="Infinite", disabled=True)
        self.use_clever_hydrogenation = ipw.Checkbox(
            description="Infer implicit hydrogens from bond orders",
            value=True,
            indent=False,
        )
        self.symmetrize_geometry = ipw.Checkbox(
            description="Clean up 2D carbon geometry",
            value=False,
            indent=False,
        )
        self.create_button = ipw.Button(
            description="Create model", button_style="success"
        )
        self.create_button.on_click(self._on_button_click)

        supported_formats = ipw.HTML(
            """
            <a href="https://pubs.acs.org/doi/10.1021/ja0697875" target="_blank">
            Supported structure formats: ".cdxml"
            </a>
            """
        )
        self.output_message = ipw.HTML(value="")

        # --- Layout ---
        super().__init__(
            children=[
                self.file_upload,
                self.nunits,
                self.use_clever_hydrogenation,
                self.symmetrize_geometry,
                supported_formats,
                self.create_button,
                self.output_message,
            ]
        )

        # --- Internal state ---
        self.structure: Optional[ase.Atoms] = None
        self.crossing_points: Optional[np.ndarray] = None
        self.cdxml_atoms: Optional[np.ndarray] = None
        self.atoms: Optional[ase.Atoms] = None
        self.whole_atoms: Optional[ase.Atoms] = None
        self._cdxml_content = None
        self._geometry_message = ""

    # ---------------- Event handlers ----------------
    def _convert_uploaded_cdxml(self) -> bool:
        """Convert the stored CDXML with the currently selected geometry options."""
        if self._cdxml_content is None:
            self.output_message.value = "Error: No CDXML file has been uploaded."
            return False
        try:
            self._geometry_message, self.atoms, self.whole_atoms = (
                self.cdxml_to_ase_from_string(
                    self._cdxml_content,
                    symmetrize=self.symmetrize_geometry.value,
                )
            )
            self.crossing_points, self.cdxml_atoms, is_not_periodic = (
                self.extract_crossing_and_atom_positions(
                    self._cdxml_content,
                    atom_positions_override=self.atoms.positions,
                )
            )
            self.nunits.disabled = bool(is_not_periodic)
            self.output_message.value = (
                f"Ready to create the structure. {self._geometry_message}"
            )
            return True
        except ValueError as exc:
            self.output_message.value = f"Error: {html.escape(str(exc))}"
        except Exception as exc:
            self.output_message.value = (
                f"Unexpected error: {html.escape(str(exc))}"
            )
        return False

    def _on_file_upload(self, change=None) -> None:
        """Handle file upload and convert CDXML to ASE Atoms."""
        upload_value = self.file_upload.value
        if change is not None:
            upload_value = change.get("new", upload_value)
        if not upload_value:
            return

        self.nunits.value = "Infinite"
        self.nunits.disabled = True

        def get_unified_representation(value):
            """Return name/content pairs for ipywidgets 7 and 8 payloads."""
            if isinstance(value, dict):
                return [
                    (filename, bytes(item["content"]))
                    for filename, item in value.items()
                ]

            files = []
            for item in value:
                if isinstance(item, dict):
                    files.append((item["name"], bytes(item["content"])))
                else:
                    files.append((item["name"], item.content.tobytes()))
            return files

        _, self._cdxml_content = get_unified_representation(upload_value)[0]
        self._convert_uploaded_cdxml()

    def _on_button_click(self, _=None) -> None:
        """Create the ASE model when 'Create model' button is clicked."""
        if not self._convert_uploaded_cdxml():
            return
        if self.atoms is None or len(self.atoms) == 0:
            self.output_message.value = "Error: No atoms available to process."
            return

        atoms = self.atoms.copy()

        if self.crossing_points is not None:
            if self.cdxml_atoms is None:
                self.output_message.value = "Error: CDXML atom positions are unavailable."
                return
            crossing_points = self.transform_points(
                self.cdxml_atoms, atoms.positions, self.crossing_points
            )
            source_atoms = (
                self.whole_atoms if self.use_clever_hydrogenation.value else self.atoms
            )
            if source_atoms is None:
                self.output_message.value = "Error: Converted atoms are unavailable."
                return
            atoms = self.align_and_trim_atoms(
                source_atoms,
                np.array(crossing_points),
                units=self.nunits.value,
                original_atoms=source_atoms,
            )
        else:
            self.output_message.value = "Error: No periodic boundaries found."
            return

        if self.nunits.disabled:
            extra_cell = 15.0
            atoms.cell = np.ptp(atoms.positions, axis=0) + extra_cell
            atoms.center()
            atoms.pbc = False

        if not self.nunits.disabled and self.nunits.value == "Infinite":
            atoms.pbc = [True, False, False]

        messages = ["Structure created.", self._geometry_message]
        if not self.use_clever_hydrogenation.value:
            hydrogen_message, atoms = self.add_safe_hydrogen_atoms(atoms)
            messages.append(hydrogen_message)
        self.output_message.value = " ".join(messages)

        self.structure = atoms

    @staticmethod
    def add_safe_hydrogen_atoms(atoms: Atoms) -> Tuple[str, Atoms]:
        """Add one H to C atoms with fewer than three neighbors."""
        neighbor_list = NeighborList(
            [covalent_radii[atom.number] for atom in atoms],
            bothways=True,
            self_interaction=False,
        )
        neighbor_list.update(atoms)

        need_hydrogen = [
            atom.index
            for atom in atoms
            if atom.symbol == "C"
            and len(neighbor_list.get_neighbors(atom.index)[0]) < 3
        ]

        for index in need_hydrogen:
            vec = np.zeros(3)
            indices, offsets = neighbor_list.get_neighbors(atoms[index].index)
            for i, offset in zip(indices, offsets):
                vec += -atoms[index].position + (
                    atoms.positions[i] + np.dot(offset, atoms.get_cell())
                )
            vec_norm = np.linalg.norm(vec)
            if vec_norm > 1e-12:
                position = -vec / vec_norm * 1.1 + atoms[index].position
            else:
                position = atoms[index].position + np.array([0.0, 0.0, 1.1])
            atoms.append(ase.Atom("H", position))

        return (
            f"Added missing Hydrogen atoms (safe hydrogenation): {need_hydrogen}.",
            atoms,
        )

    # ---------------- Core conversion logic ----------------
    @staticmethod
    def symmetrize_carbon_network(
        positions: np.ndarray,
        symbols: List[str],
        bonds: List[Tuple[int, int]],
        target_cc_length: float = 1.43,
        minimum_cc_length: float = 1.35,
        maximum_cc_length: float = 1.60,
    ) -> np.ndarray:
        """Relax a carbon drawing while preserving its planar graph embedding.

        The local sp2 preference is deliberately soft. Ring closure and fused
        edges therefore distribute strain globally instead of forcing each
        5-, 6-, or 7-membered face to become an independent regular polygon.
        """
        positions = np.asarray(positions, dtype=float)
        carbon_indices = [
            index for index, symbol in enumerate(symbols) if symbol == "C"
        ]
        local_index = {
            atom_index: carbon_index
            for carbon_index, atom_index in enumerate(carbon_indices)
        }
        carbon_edges = [
            (local_index[first], local_index[second])
            for first, second in bonds
            if first in local_index and second in local_index
        ]
        if len(carbon_edges) < 3:
            return positions.copy()

        original = positions[carbon_indices, :2].copy()
        if _has_bond_crossings(original, carbon_edges):
            raise ValueError(
                "the input carbon bonds already contain a geometric crossing"
            )

        adjacency = [[] for _ in range(len(original))]
        for first, second in carbon_edges:
            adjacency[first].append(second)
            adjacency[second].append(first)

        angle_terms = []
        for center, neighbors in enumerate(adjacency):
            if len(neighbors) not in (2, 3):
                continue
            for first_index in range(len(neighbors)):
                for second_index in range(first_index + 1, len(neighbors)):
                    angle_terms.append(
                        (center, neighbors[first_index], neighbors[second_index])
                    )

        faces = _bounded_faces(original, carbon_edges)
        face_areas = [
            (face, _signed_area(original[face]))
            for face in faces
            if abs(_signed_area(original[face])) > 1.0e-8
        ]

        def residual(flat_positions):
            current = flat_positions.reshape((-1, 2))
            values: list[float] = [
                float(
                    (np.linalg.norm(current[second] - current[first]) - target_cc_length)
                    / 0.04
                )
                for first, second in carbon_edges
            ]
            for center, first, second in angle_terms:
                first_vector = current[first] - current[center]
                second_vector = current[second] - current[center]
                denominator = np.linalg.norm(first_vector) * np.linalg.norm(
                    second_vector
                )
                cosine = np.dot(first_vector, second_vector) / max(denominator, 1.0e-12)
                values.append(float(math.sqrt(0.10) * (cosine + 0.5) / 0.15))

            # Keep the user's global layout while allowing local cleanup.
            values.extend((math.sqrt(0.10) * (current - original) / 0.20).ravel())

            # This barrier protects every detected face from collapse or inversion.
            for face, original_area in face_areas:
                area_ratio = _signed_area(current[face]) / original_area
                values.append(math.sqrt(20.0) * max(0.0, 0.35 - area_ratio))
            return np.asarray(values)

        maximum_displacement = 0.75
        result = least_squares(
            residual,
            original.ravel(),
            bounds=(
                (original - maximum_displacement).ravel(),
                (original + maximum_displacement).ravel(),
            ),
            max_nfev=200,
            ftol=1.0e-9,
            xtol=1.0e-9,
            gtol=1.0e-9,
        )
        if not result.success:
            raise ValueError(f"geometry optimizer did not converge: {result.message}")

        optimized = result.x.reshape((-1, 2))
        lengths = np.array(
            [
                np.linalg.norm(optimized[second] - optimized[first])
                for first, second in carbon_edges
            ]
        )
        if (
            np.min(lengths) < minimum_cc_length - 1.0e-6
            or np.max(lengths) > maximum_cc_length + 1.0e-6
        ):
            raise ValueError(
                "optimized C-C lengths fall outside "
                f"{minimum_cc_length:.2f}-{maximum_cc_length:.2f} Å"
            )
        if _has_bond_crossings(optimized, carbon_edges):
            raise ValueError("geometry cleanup would create crossing carbon bonds")

        for face, original_area in face_areas:
            optimized_area = _signed_area(optimized[face])
            if optimized_area * original_area <= 0.0 or abs(
                optimized_area
            ) < 0.25 * abs(original_area):
                raise ValueError(
                    "geometry cleanup would invert or collapse a carbon face"
                )

        updated = positions.copy()
        carbon_displacements = optimized - original
        updated[carbon_indices, :2] = optimized

        # Move explicit substituents with the carbon atoms to which they are bound.
        carbon_neighbors = {index: [] for index in range(len(positions))}
        for first, second in bonds:
            if first in local_index and second not in local_index:
                carbon_neighbors[second].append(first)
            if second in local_index and first not in local_index:
                carbon_neighbors[first].append(second)
        for atom_index, neighbors in carbon_neighbors.items():
            if not neighbors or atom_index in local_index:
                continue
            displacement = np.mean(
                [carbon_displacements[local_index[index]] for index in neighbors],
                axis=0,
            )
            updated[atom_index, :2] += displacement

        return updated

    @staticmethod
    def cdxml_to_ase_from_string(
        cdxml_content: str | bytes,
        target_cc_length: float = 1.43,
        symmetrize: bool = False,
    ) -> Tuple[str, Atoms, Atoms]:
        """
        Convert CDXML content (string) into ASE Atoms objects:
        one bare molecule (no hydrogens) and one with hydrogens.
        """
        root = ET.fromstring(cdxml_content)

        # --- Element and bond maps ---
        element_map = {
            "1": "H",
            "5": "B",
            "6": "C",
            "7": "N",
            "8": "O",
            "9": "F",
            "15": "P",
            "16": "S",
            "17": "Cl",
            "26": "Fe",
            "27": "Co",
            "28": "Ni",
            "22": "Ti",
            "40": "Zr",
            "65": "Tb",
            "35": "Br",
            "53": "I",
        }

        default_valence = {
            "H": 1,
            "B": 3,
            "C": 4,
            "N": 3,
            "O": 2,
            "F": 1,
            "P": 3,
            "S": 2,
            "Cl": 1,
            "Br": 1,
            "I": 1,
            "Fe": 2,
            "Co": 2,
            "Ni": 2,
            "Ti": 4,
            "Zr": 4,
            "Tb": 3,
        }

        bond_order_map = {
            "1": 1.0,  # single bond
            "2": 2.0,  # double bond
            "3": 3.0,  # triple bond
            "A": 1.5,  # aromatic bond
        }

        atoms, bonds, radicals = {}, [], set()

        # --- Parse atoms ---
        for n in root.iter("n"):
            a_id = n.attrib["id"]
            el = element_map.get(n.attrib.get("Element", ""), "C")
            x, y = map(float, n.attrib["p"].split())
            atoms[a_id] = {"el": el, "pos": np.array([x, y, 0.0])}
            if "Radical" in n.attrib:
                radicals.add(a_id)

        for g in root.iter("graphic"):
            if g.attrib.get("SymbolType") == "Electron":
                for rep in g.iter("represent"):
                    target = rep.attrib.get("object")
                    if target:
                        radicals.add(target)

        # --- Parse bonds ---
        for b in root.iter("b"):
            a1, a2 = b.attrib["B"], b.attrib["E"]
            order = bond_order_map.get(b.attrib.get("Order", "1"), 1.0)
            bonds.append({"a1": a1, "a2": a2, "order": order})

        # --- Scale from explicit C-C bonds, never from unrelated close atoms ---
        cc_lengths = [
            np.linalg.norm(atoms[bond["a1"]]["pos"] - atoms[bond["a2"]]["pos"])
            for bond in bonds
            if atoms[bond["a1"]]["el"] == atoms[bond["a2"]]["el"] == "C"
        ]
        scale = target_cc_length / np.median(cc_lengths) if cc_lengths else 1.0
        for atom in atoms.values():
            atom["pos"] *= scale

        geometry_message = "Original CDXML geometry retained."
        if symmetrize:
            atom_ids = list(atoms)
            atom_index = {atom_id: index for index, atom_id in enumerate(atom_ids)}
            positions = np.array([atoms[atom_id]["pos"] for atom_id in atom_ids])
            symbols = [atoms[atom_id]["el"] for atom_id in atom_ids]
            edge_indices = [
                (atom_index[bond["a1"]], atom_index[bond["a2"]]) for bond in bonds
            ]
            try:
                positions = CdxmlUploadWidget.symmetrize_carbon_network(
                    positions,
                    symbols,
                    edge_indices,
                    target_cc_length=target_cc_length,
                )
            except ValueError as exc:
                geometry_message = (
                    "⚠️ Carbon geometry cleanup skipped: "
                    f"{exc}. Original scaled geometry retained."
                )
            else:
                for atom_id, position in zip(atom_ids, positions):
                    atoms[atom_id]["pos"] = position
                geometry_message = (
                    "Carbon geometry cleaned globally; planar embedding preserved "
                    "and C-C bonds constrained to 1.35-1.60 Å."
                )

        # --- Connectivity ---
        conn = {k: [] for k in atoms}
        for b in bonds:
            conn[b["a1"]].append((b["a2"], b["order"]))
            conn[b["a2"]].append((b["a1"], b["order"]))

        # --- Bare molecule ---
        bare_pos = [a["pos"] for a in atoms.values()]
        bare_sym = [a["el"] for a in atoms.values()]
        bare_mol = Atoms(symbols=bare_sym, positions=bare_pos)

        # --- Determine implicit hydrogens ---
        impl_H = {}
        for aid, a in atoms.items():
            el = a["el"]
            total = sum(o for _, o in conn[aid])
            val = default_valence.get(el, 4)
            if aid in radicals:
                val -= 1
            impl_H[aid] = max(0, round(val - total))

        # --- Add hydrogens ---
        pos, sym = list(bare_pos), list(bare_sym)
        for aid, nH in impl_H.items():
            if nH == 0:
                continue

            el = atoms[aid]["el"]
            c = atoms[aid]["pos"]
            neighbors = [normalize(atoms[n]["pos"] - c) for n, _ in conn[aid]]
            orders = [o for _, o in conn[aid]]

            def add_H(vecs: List[np.ndarray], length: float = 1.09):
                for v in vecs:
                    pos.append(c + length * v)
                    sym.append("H")

            # --- Oxygen or Nitrogen (improved geometry) ---
            if el in ("O", "N"):
                v_sum = np.sum(neighbors, axis=0) if neighbors else np.zeros(3)
                base_dir = (
                    normalize(-v_sum)
                    if np.linalg.norm(v_sum) > 1e-6
                    else np.array([0, 0, 1])
                )

                # --- Single hydrogen (OH, NH) ---
                if nH == 1:
                    if el == "O" and len(neighbors) == 1:
                        # OH: tilt the H about 35° out of the opposite direction (~105° angle)
                        v = neighbors[0]
                        # Keep hydrogen roughly in the same molecular plane
                        rot_axis = np.array([0, 0, 1])
                        if np.allclose(np.abs(np.dot(v, rot_axis)), 1.0):
                            rot_axis = np.array([1, 0, 0])
                        dirs = [rotate_vector(-v, rot_axis, math.radians(35))]
                        add_H(dirs, 0.98)
                    else:
                        # Default for NH etc.
                        add_H([base_dir], 1.00 if el == "N" else 0.98)
                    continue

                # --- Two hydrogens (H2O, NH2) ---
                if nH == 2:
                    theta = math.radians(104.5 if el == "O" else 107.0)
                    rot_axis = np.array([0, 0, 1])
                    if np.allclose(np.abs(np.dot(base_dir, rot_axis)), 1.0):
                        rot_axis = np.array([1, 0, 0])
                    dirs = [
                        rotate_vector(base_dir, rot_axis, math.radians(a))
                        for a in (-theta / 2, theta / 2)
                    ]
                    add_H(dirs, 0.98 if el == "O" else 1.00)
                    continue

            # --- Other heteroatoms (unchanged behaviour) ---
            if el != "C":
                avg = (
                    normalize(-np.sum(neighbors, axis=0))
                    if neighbors
                    else np.array([0, 0, 1])
                )
                add_H([avg], 1.01)
                continue

            # --- Carbon atoms (original logic, untouched) ---

            # CH3
            if nH == 3 and len(neighbors) == 1:
                v = neighbors[0]
                theta = math.radians(109.47)
                dirs = [
                    np.array(
                        [
                            math.sin(theta) * math.cos(p),
                            math.sin(theta) * math.sin(p),
                            math.cos(theta),
                        ]
                    )
                    for p in (0, 2 * math.pi / 3, 4 * math.pi / 3)
                ]
                R = rotation_matrix_from_vectors(np.array([0, 0, 1]), -v)
                add_H([-R @ d for d in dirs], 1.10)
                continue

            # CH2
            if nH == 2:
                CH_len = 1.09 if any(o >= 1.5 for o in orders) else 1.10
                if len(neighbors) == 1:
                    v = neighbors[0]
                    if any(o >= 1.5 for o in orders):
                        normal = np.array([0, 0, 1])
                        bis = -v
                        add_H(
                            [
                                rotate_vector(bis, normal, math.radians(a))
                                for a in (60, -60)
                            ],
                            CH_len,
                        )
                    else:
                        theta = math.radians(109.47)
                        dirs = [
                            np.array(
                                [
                                    math.sin(theta) * math.cos(p),
                                    math.sin(theta) * math.sin(p),
                                    math.cos(theta),
                                ]
                            )
                            for p in (0, 2 * math.pi / 3)
                        ]
                        R = rotation_matrix_from_vectors(np.array([0, 0, 1]), -v)
                        add_H([R @ d for d in dirs], CH_len)
                    continue

                if len(neighbors) == 2:
                    v1, v2 = neighbors
                    bis = normalize(-(v1 + v2))
                    plane_normal = normalize(np.cross(v1, v2))
                    if any(o >= 1.5 for o in orders):
                        add_H(
                            [
                                rotate_vector(bis, plane_normal, math.radians(a))
                                for a in (60, -60)
                            ],
                            CH_len,
                        )
                    else:
                        angle = math.radians(54.75)
                        perp = normalize(np.cross(v1, v2))
                        add_H(
                            [
                                math.cos(angle) * bis + math.sin(angle) * perp,
                                math.cos(angle) * bis - math.sin(angle) * perp,
                            ],
                            CH_len,
                        )
                    continue

            # CH
            if nH == 1:
                avg = normalize(-np.sum(neighbors, axis=0))
                add_H([avg], 1.09)

        mol = Atoms(symbols=sym, positions=pos)
        msg = geometry_message
        return msg, bare_mol, mol

    # ---------------- Geometry utilities ----------------
    @staticmethod
    def transform_points(
        set1: np.ndarray, set2: np.ndarray, points: np.ndarray
    ) -> List[List[float]]:
        """Transform points based on scaling and rotation aligning set1→set2."""
        centroid1, centroid2 = np.mean(set1, axis=0), np.mean(set2, axis=0)
        centered1, centered2 = set1 - centroid1, set2 - centroid2
        scale = (
            np.linalg.norm(centered2, axis=1).mean()
            / np.linalg.norm(centered1, axis=1).mean()
        )
        cross_cov = np.dot(centered1.T, centered2)
        u, _, vt = np.linalg.svd(cross_cov)
        rotation_m = np.dot(vt.T, u.T)
        return (scale * np.dot(points - centroid1, rotation_m.T) + centroid2).tolist()

    @staticmethod
    def max_extension_points(points: np.ndarray) -> np.ndarray:
        """Return two points defining the maximum extension of a set of 3D points."""
        x_range, y_range = np.ptp(points[:, 0]), np.ptp(points[:, 1])
        if x_range >= y_range:
            minx, maxx = np.min(points[:, 0]), np.max(points[:, 0])
            return np.array([[minx - 7.5, 0, 0], [maxx + 7.5, 0, 0]])
        miny, maxy = np.min(points[:, 1]), np.max(points[:, 1])
        return np.array([[0, miny - 7.5, 0], [0, maxy + 7.5, 0]])

    # ---------------- CDXML analysis ----------------
    def extract_crossing_and_atom_positions(
        self,
        cdxml_content: str | bytes,
        atom_positions_override: Optional[np.ndarray] = None,
    ) -> Tuple[Optional[np.ndarray], np.ndarray, bool]:
        """Extract robust periodic boundaries and atom positions from CDXML.

        ChemDraw may serialize the right bracket before the left bracket. Crossing
        matching must therefore be independent of both XML order and vector sign.
        """
        root = ET.fromstring(cdxml_content)

        atom_positions, atom_id_map = [], {}
        for node in root.findall(".//n"):
            atom_id = node.get("id")
            if atom_id and "p" in node.attrib:
                x, y = map(float, node.attrib["p"].split())
                atom_positions.append((x, y, 0.0))
                atom_id_map[atom_id] = len(atom_positions) - 1
        atom_positions = np.asarray(atom_positions, dtype=float)
        drawing_atom_positions = atom_positions.copy()

        if atom_positions_override is not None:
            override = np.asarray(atom_positions_override, dtype=float)
            if len(override) != len(atom_positions):
                raise ValueError(
                    "atom position override does not match the CDXML atom count"
                )
            if override.shape[1] == 2:
                override = np.column_stack([override, np.zeros(len(override))])
            if override.shape != atom_positions.shape:
                raise ValueError(
                    "atom position override must have shape (N, 2) or (N, 3)"
                )
            atom_positions = override.copy()

        bonds_by_id = {
            bond.get("id"): bond for bond in root.findall(".//b") if bond.get("id")
        }

        def bond_midpoint(bond_id):
            bond = bonds_by_id.get(bond_id)
            if bond is None:
                return None
            first, second = bond.get("B"), bond.get("E")
            if first not in atom_id_map or second not in atom_id_map:
                return None
            return 0.5 * (
                atom_positions[atom_id_map[first]] + atom_positions[atom_id_map[second]]
            )

        bracket_centers = {}
        for graphic in root.iter("graphic"):
            if (
                graphic.attrib.get("BracketType") != "Square"
                or "BoundingBox" not in graphic.attrib
            ):
                continue
            coordinates = [
                float(value) for value in graphic.attrib["BoundingBox"].split()
            ]
            if len(coordinates) != 4:
                continue
            x_min, y_min, x_max, y_max = coordinates
            bracket_centers[graphic.get("id")] = np.array(
                [(x_min + x_max) / 2, (y_min + y_max) / 2, 0.0]
            )

        if atom_positions_override is not None and bracket_centers:
            bracket_ids = list(bracket_centers)
            transformed_centers = self.transform_points(
                drawing_atom_positions,
                atom_positions,
                np.array([bracket_centers[bracket_id] for bracket_id in bracket_ids]),
            )
            bracket_centers = {
                bracket_id: np.asarray(center)
                for bracket_id, center in zip(bracket_ids, transformed_centers)
            }

        if not bracket_centers:
            return self.max_extension_points(atom_positions), atom_positions, True

        def matched_boundary_points(
            first_center,
            second_center,
            first_crossings,
            second_crossings,
        ):
            bracket_vector = second_center[:2] - first_center[:2]
            bracket_distance = np.linalg.norm(bracket_vector)
            if bracket_distance < 1.0e-12:
                return None
            axis = bracket_vector / bracket_distance
            transverse_axis = np.array([-axis[1], axis[0]])
            matched_pairs = []
            for first_point in first_crossings:
                for second_point in second_crossings:
                    vector = second_point[:2] - first_point[:2]
                    distance = np.linalg.norm(vector)
                    if distance < 1.0e-12:
                        continue
                    alignment = abs(np.dot(vector / distance, axis))
                    transverse = abs(np.dot(vector, transverse_axis))
                    projection = abs(np.dot(vector, axis))
                    if alignment > 0.99 and transverse < max(
                        0.5, 0.05 * bracket_distance
                    ):
                        matched_pairs.append(
                            (
                                transverse,
                                abs(projection - bracket_distance),
                                -alignment,
                                np.array([first_point, second_point]),
                            )
                        )
            if not matched_pairs:
                return None

            best_pair = min(
                matched_pairs,
                key=lambda pair: (pair[0], pair[1], pair[2]),
            )
            return (
                -best_pair[2],
                -best_pair[0],
                best_pair[3],
            )

        candidates = []
        for group in root.findall(".//bracketedgroup"):
            attachments = []
            for attachment in group.findall("./bracketattachment"):
                graphic_id = attachment.get("GraphicID")
                if graphic_id not in bracket_centers:
                    continue
                points = []
                for crossing in attachment.findall("./crossingbond"):
                    midpoint = bond_midpoint(crossing.get("BondID"))
                    if midpoint is not None:
                        points.append(midpoint)
                if points:
                    attachments.append(
                        (bracket_centers[graphic_id], np.asarray(points))
                    )

            for first_index in range(len(attachments)):
                for second_index in range(first_index + 1, len(attachments)):
                    candidate = matched_boundary_points(
                        attachments[first_index][0],
                        attachments[second_index][0],
                        attachments[first_index][1],
                        attachments[second_index][1],
                    )
                    if candidate is not None:
                        candidates.append(candidate)

        if candidates:
            _, _, boundaries = max(
                candidates, key=lambda candidate: (candidate[0], candidate[1])
            )
            return boundaries, atom_positions, False

        # Compatibility path for CDXML writers that omit bracketattachment groups.
        centers = list(bracket_centers.values())
        crossing_points = [
            midpoint
            for crossing in root.findall(".//crossingbond")
            if (midpoint := bond_midpoint(crossing.get("BondID"))) is not None
        ]
        if len(centers) == 2 and crossing_points:
            candidate = matched_boundary_points(
                centers[0],
                centers[1],
                crossing_points,
                crossing_points,
            )
            if candidate is not None:
                return candidate[2], atom_positions, False

        # Square brackets still define a repeat interval even when a writer does
        # not provide usable crossing-bond metadata.
        if len(centers) == 2:
            return np.asarray(centers), atom_positions, False

        return None, atom_positions, True

    # ---------------- Alignment & trimming ----------------
    @staticmethod
    def align_and_trim_atoms(
        atoms: Atoms,
        crossing_points: np.ndarray,
        units: Optional[str] = None,
        original_atoms: Optional[Atoms] = None,
    ) -> Atoms:
        """
        Align, trim, and optionally replicate atoms along the periodic direction.
        Restores hydrogens lost during trimming using original geometry.
        """
        assert crossing_points.shape == (2, 3), (
            "crossing_points must be a 2x3 NumPy array."
        )

        vector = crossing_points[1] - crossing_points[0]
        norm_vector = np.linalg.norm(vector)
        angle = np.arctan2(vector[1], vector[0])

        def rotate_atoms(atoms_obj: Atoms) -> Atoms:
            atoms_copy = atoms_obj.copy()
            atoms_copy.rotate(-np.degrees(angle), "z", center=(0, 0, 0))
            return atoms_copy

        atoms_rot = rotate_atoms(atoms)
        orig_rot = rotate_atoms(original_atoms if original_atoms is not None else atoms)

        rotation_matrix = np.array(
            [
                [np.cos(-angle), -np.sin(-angle), 0],
                [np.sin(-angle), np.cos(-angle), 0],
                [0, 0, 1],
            ]
        )
        rotated_cp = np.dot(crossing_points, rotation_matrix.T)
        x_min, x_max = min(rotated_cp[:, 0]), max(rotated_cp[:, 0]) + 0.1

        pos = atoms_rot.get_positions()
        mask_main, mask_tail, mask_head = (
            (pos[:, 0] > x_min) & (pos[:, 0] <= x_max),
            pos[:, 0] <= x_min,
            pos[:, 0] > x_max,
        )
        bounded_atoms, tail_atoms, head_atoms = (
            atoms_rot[mask_main].copy(),
            atoms_rot[mask_tail].copy(),
            atoms_rot[mask_head].copy(),
        )
        kept_indices = np.where(mask_main)[0]

        nl = NeighborList(
            [covalent_radii[num] * 1.2 for num in orig_rot.numbers],
            self_interaction=False,
            bothways=True,
        )
        nl.update(orig_rot)
        symbols = orig_rot.get_chemical_symbols()

        restored_positions, restored_symbols = [], []
        for i in kept_indices:
            if symbols[i] == "H":
                continue
            indices, _ = nl.get_neighbors(i)
            for j in indices:
                if symbols[j] == "H":
                    h_pos = orig_rot.positions[j]
                    if not (x_min < h_pos[0] <= x_max):
                        restored_positions.append(h_pos)
                        restored_symbols.append("H")

        if restored_positions:
            bounded_atoms += ase.Atoms(restored_symbols, positions=restored_positions)

        if units is None:
            n_units = None
        else:
            try:
                n_units = int(units)
            except ValueError:
                n_units = None

        if n_units is None or n_units < 1:
            atoms_final = bounded_atoms
        else:
            replicated_atoms = bounded_atoms.copy()
            for ni in range(1, n_units):
                shifted = bounded_atoms.get_positions() + np.array(
                    [ni * norm_vector, 0, 0]
                )
                replicated_atoms += ase.Atoms(
                    bounded_atoms.get_chemical_symbols(), positions=shifted
                )
            shifted_head = head_atoms.get_positions() + np.array(
                [(n_units - 1) * norm_vector, 0, 0]
            )
            replicated_atoms += ase.Atoms(
                head_atoms.get_chemical_symbols(), positions=shifted_head
            )
            replicated_atoms += tail_atoms
            atoms_final = replicated_atoms

        # Hydrogens restored across a periodic cut can overlap a carbon on the
        # opposite boundary. Such atoms are trimming artefacts, not chemistry.
        symbols = np.asarray(atoms_final.get_chemical_symbols())
        hydrogen_indices = np.where(symbols == "H")[0]
        heavy_indices = np.where(symbols != "H")[0]
        keep = np.ones(len(atoms_final), dtype=bool)
        for hydrogen_index in hydrogen_indices:
            if not len(heavy_indices):
                keep[hydrogen_index] = False
                continue
            nearest_heavy = np.min(
                np.linalg.norm(
                    atoms_final.positions[heavy_indices]
                    - atoms_final.positions[hydrogen_index],
                    axis=1,
                )
            )
            if nearest_heavy < 0.70 or nearest_heavy > 1.35:
                keep[hydrogen_index] = False
        atoms_final = atoms_final[keep]

        if n_units is None or n_units < 1:
            l1, atoms_final.pbc = norm_vector, [True, False, False]
        else:
            l1 = np.ptp(atoms_final.get_positions()[:, 0]) + 15.0
        l2 = 15.0 + np.ptp(atoms_final.get_positions()[:, 1])
        l3 = 15.0
        atoms_final.set_cell([l1, l2, l3])
        atoms_final.center()

        return atoms_final

import ase
import ipywidgets as ipw
import numpy as np
import spglib
import traitlets as tl
from aiida.orm.nodes.data.structure import _get_dimensionality
from weas_widget.base_widget import BaseWidget as _BaseWidget
from weas_widget.utils import ASEAdapter

from aiidalab_widgets_base.utils import ase2spglib


class BaseWidget(_BaseWidget):
    # this is not used but needed for compatibility
    _camera_orientation = tl.List()


class WeasWidgetViewer(ipw.HBox):
    """A structure viewer widget for AiiDAlab using WeasWidget."""

    # For compatibility with AiiDAlab-Widget-Base StructureManagerWidget
    input_selection = tl.List(tl.Int(), allow_none=True)
    selection = tl.List(tl.Int())
    structure = tl.Instance(ase.Atoms, allow_none=True)

    _CELL_LABELS = {
        1: ["length", "Å"],
        2: ["area", "Å²"],
        3: ["volume", "Å³"],
    }

    def __init__(self, **kwargs):
        self._viewer = BaseWidget(**kwargs)
        self._viewer.modelStyle = 1  # Set to "Ball and Stick" style
        tl.link((self, "selection"), (self._viewer, "selectedAtomsIndices"))
        super().__init__([self._viewer, self._cell_tab()])

    # For compatibility with AiiDAlab-Widget-Base StructureManagerWidget
    @tl.observe("structure")
    def _observe_structure(self, change):
        if self.structure is not None:
            self._viewer.atoms = ASEAdapter.to_weas(self.structure)
        self.cell = self.structure.cell if self.structure else None

    @tl.observe("structure")
    def _observe_cell(self, _=None):
        # Updtate the Cell and Periodicity.
        if self.structure and self.structure.cell:
            self._update_cell_tab()
        else:
            self._reset_cell_tab()

    @tl.observe("selection")
    def _observe_selection(self, _=None):
        if self.structure and self.structure.cell:
            self._update_cell_tab()
        else:
            self._reset_cell_tab()

    def _update_cell_tab(self):
        self.cell = self.structure.cell
        cell_array = self.cell.array
        lengths = self.cell.lengths()
        angles = self.cell.angles()

        spglib_structure = ase2spglib(self.structure)
        symmetry_dataset = spglib.get_symmetry_dataset(
            spglib_structure, symprec=1e-5, angle_tolerance=1.0
        )
        # Calculate the volume of the cell using the function from orm.StructureData
        dimension_data = _get_dimensionality(self.structure.pbc, self.cell)
        # Determine the label and unit based on dimensionality
        cell_label = self._CELL_LABELS.get(dimension_data["dim"])
        if cell_label:
            cell_volume = (
                f"Cell {cell_label[0]}: {dimension_data['value']:.4f} ({cell_label[1]})"
            )
        else:
            cell_volume = "Cell volume: -"

        self.cell_info.value = (
            "<div style='font-size: 13px; font-weight: 600; margin-bottom: 8px;'>"
            "Structure info"
            "</div>"
            "<div style='font-size: 13px; line-height: 1.4;'>"
            "<table style='width: 100%; border-collapse: collapse;'>"
            "<tr>"
            "<th style='text-align: left; padding: 4px 24px 4px 0; "
            "border-bottom: 1px solid #e0e0e0;'>Cell vectors (Å)</th>"
            "<th style='text-align: left; padding: 4px 12px; "
            "border-bottom: 1px solid #e0e0e0;'>Vector length (Å)</th>"
            "<th style='text-align: left; padding: 4px 0; "
            "border-bottom: 1px solid #e0e0e0;'>Angles (°)</th>"
            "</tr>"
            "<tr>"
            "<td style='padding: 6px 24px 2px 0;'>"
            f"<i><b>a</b></i>: {cell_array[0][0]:.4f} {cell_array[0][1]:.4f} {cell_array[0][2]:.4f}"
            "</td>"
            "<td style='padding: 6px 12px 2px 0;'>"
            f"|<i><b>a</b></i>|: {lengths[0]:.4f}"
            "</td>"
            "<td style='padding: 6px 0 2px 0;'>"
            f"&alpha;: {angles[0]:.4f}"
            "</td>"
            "</tr>"
            "<tr>"
            "<td style='padding: 2px 24px 2px 0;'>"
            f"<i><b>b</b></i>: {cell_array[1][0]:.4f} {cell_array[1][1]:.4f} {cell_array[1][2]:.4f}"
            "</td>"
            "<td style='padding: 2px 12px 2px 0;'>"
            f"|<i><b>b</b></i>|: {lengths[1]:.4f}"
            "</td>"
            "<td style='padding: 2px 0 2px 0;'>"
            f"&beta;: {angles[1]:.4f}"
            "</td>"
            "</tr>"
            "<tr>"
            "<td style='padding: 2px 24px 6px 0;'>"
            f"<i><b>c</b></i>: {cell_array[2][0]:.4f} {cell_array[2][1]:.4f} {cell_array[2][2]:.4f}"
            "</td>"
            "<td style='padding: 2px 12px 6px 0;'>"
            f"|<i><b>c</b></i>|: {lengths[2]:.4f}"
            "</td>"
            "<td style='padding: 2px 0 6px 0;'>"
            f"&gamma;: {angles[2]:.4f}"
            "</td>"
            "</tr>"
            "</table>"
            "<div style='margin-top: 8px; padding-top: 6px; "
            "border-top: 1px solid #e0e0e0;'>"
            "<div style='font-weight: 600; margin-bottom: 4px;'>"
            "Symmetry information"
            "</div>"
            "<div>"
            "Spacegroup: "
            f"{symmetry_dataset['international']} (No.{symmetry_dataset['number']})"
            "</div>"
            "<div>"
            f"Hall: {symmetry_dataset['hall']} (No.{symmetry_dataset['hall_number']})"
            "</div>"
            "<div>"
            f"Periodicity: {self._periodicity_label(self.structure.pbc)}"
            "</div>"
            "<div style='margin-top: 4px; font-weight: 600;'>"
            f"{cell_volume}"
            "</div>"
            "</div>"
            "<div style='margin-top: 10px; padding-top: 6px; "
            "border-top: 1px solid #e0e0e0;'>"
            "<div style='font-weight: 600; margin-bottom: 4px;'>"
            "Selection"
            "</div>"
            f"{self._selection_info_html()}"
            "</div>"
            "</div>"
        )

    def _reset_cell_tab(self):
        self.cell_info.value = (
            "<div style='font-size: 13px; font-weight: 600; margin-bottom: 8px;'>"
            "Structure info"
            "</div>"
            "<div style='font-size: 13px; line-height: 1.4;'>"
            "<table style='width: 100%; border-collapse: collapse;'>"
            "<tr>"
            "<th style='text-align: left; padding: 4px 24px 4px 0; "
            "border-bottom: 1px solid #e0e0e0;'>Cell vectors (Å)</th>"
            "<th style='text-align: left; padding: 4px 12px; "
            "border-bottom: 1px solid #e0e0e0;'>Vector length (Å)</th>"
            "<th style='text-align: left; padding: 4px 0; "
            "border-bottom: 1px solid #e0e0e0;'>Angles (°)</th>"
            "</tr>"
            "<tr>"
            "<td style='padding: 6px 24px 2px 0;'><i><b>a</b></i>:</td>"
            "<td style='padding: 6px 12px 2px 0;'>|<i><b>a</b></i>|:</td>"
            "<td style='padding: 6px 0 2px 0;'>&alpha;:</td>"
            "</tr>"
            "<tr>"
            "<td style='padding: 2px 24px 2px 0;'><i><b>b</b></i>:</td>"
            "<td style='padding: 2px 12px 2px 0;'>|<i><b>b</b></i>|:</td>"
            "<td style='padding: 2px 0 2px 0;'>&beta;:</td>"
            "</tr>"
            "<tr>"
            "<td style='padding: 2px 24px 6px 0;'><i><b>c</b></i>:</td>"
            "<td style='padding: 2px 12px 6px 0;'>|<i><b>c</b></i>|:</td>"
            "<td style='padding: 2px 0 6px 0;'>&gamma;:</td>"
            "</tr>"
            "</table>"
            "<div style='margin-top: 8px; padding-top: 6px; "
            "border-top: 1px solid #e0e0e0;'>"
            "<div style='font-weight: 600; margin-bottom: 4px;'>"
            "Symmetry information"
            "</div>"
            "<div>Spacegroup:</div>"
            "<div>Hall:</div>"
            "<div>Periodicity:</div>"
            "<div style='margin-top: 4px; font-weight: 600;'>"
            "Cell volume: -"
            "</div>"
            "</div>"
            "<div style='margin-top: 10px; padding-top: 6px; "
            "border-top: 1px solid #e0e0e0;'>"
            "<div style='font-weight: 600; margin-bottom: 4px;'>"
            "Selection"
            "</div>"
            "<div>Selection: -</div>"
            "</div>"
            "</div>"
        )

    def _cell_tab(self):
        self.cell_info = ipw.HTML()

        self._observe_cell()

        return ipw.VBox([self.cell_info])

    def _selection_info_html(self):
        if not self.selection:
            return "<div>Atom: -</div>"

        indices = list(self.selection)
        symbols = self.structure.get_chemical_symbols()

        if len(indices) == 1:
            index = indices[0]
            symbol = symbols[index]
            position = self.structure.positions[index]
            return (
                f"<div>Atom: {symbol}</div>"
                f"<div>Position: {position[0]:.4f} "
                f"{position[1]:.4f} {position[2]:.4f} Å</div>"
            )

        if len(indices) == 2:
            symbol_pair = f"{symbols[indices[0]]}, {symbols[indices[1]]}"
            distance = self.structure.get_distance(indices[0], indices[1], mic=True)
            return (
                f"<div>Atoms: {symbol_pair}</div><div>Distance: {distance:.4f} Å</div>"
            )

        if len(indices) == 3:
            positions = self.structure.positions[indices]
            angles = self._triangle_angles(positions)
            return (
                f"<div>Atoms: {symbols[indices[0]]}, {symbols[indices[1]]}, {symbols[indices[2]]}</div>"
                "<div>Angles:</div>"
                f"<div>at 1: {angles[0]:.2f}°</div>"
                f"<div>at 2: {angles[1]:.2f}°</div>"
                f"<div>at 3: {angles[2]:.2f}°</div>"
            )

        counts = {}
        ordered_symbols = []
        for index in indices:
            symbol = symbols[index]
            if symbol not in counts:
                ordered_symbols.append(symbol)
                counts[symbol] = 0
            counts[symbol] += 1

        counts_text = ", ".join(
            f"{counts[symbol]} {symbol}" for symbol in ordered_symbols
        )
        return f"<div>Atoms: {counts_text}</div>"

    @staticmethod
    def _periodicity_label(pbc):
        axes = [axis for axis, is_periodic in zip("xyz", pbc) if is_periodic]
        return "".join(axes) if axes else "-"

    @staticmethod
    def _triangle_angles(positions):
        p0, p1, p2 = positions
        angle0 = WeasWidgetViewer._angle_between(p1 - p0, p2 - p0)
        angle1 = WeasWidgetViewer._angle_between(p0 - p1, p2 - p1)
        angle2 = WeasWidgetViewer._angle_between(p0 - p2, p1 - p2)
        return (angle0, angle1, angle2)

    @staticmethod
    def _angle_between(vec1, vec2):
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        cos_theta = np.dot(vec1, vec2) / (norm1 * norm2)
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
        return float(np.degrees(np.arccos(cos_theta)))

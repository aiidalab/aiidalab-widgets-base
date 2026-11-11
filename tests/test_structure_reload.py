"""Explicit database reloads through the real importer/manager/viewer chain."""

import ase
import numpy as np
import pytest
from aiida import orm

import aiidalab_widgets_base as awb


@pytest.fixture(scope="session", autouse=True)
def aiida_profile(aiida_config, aiida_profile_factory):
    """These widget tests need only isolated SQLite storage, never a broker."""
    with aiida_profile_factory(aiida_config, broker_backend=None) as profile:
        yield profile


def make_source(node_class):
    atoms = ase.Atoms("CH", positions=[[5, 5, 5], [5, 5, 6.1]], cell=[12] * 3)
    node = getattr(orm, node_class)(ase=atoms)
    node.label = "Stored source"
    node.description = "Original geometry must survive explicit reload"
    style = awb.viewers.encode_representation_style_id(
        representation_type="ballstick", size=3, color="blue", token="reload"
    )
    node.base.extras.set(awb.viewers.VIEWER_REPRESENTATIONS_EXTRA, {style: [1, 1]})
    return node.store()


def load(browser, node):
    browser.pk_input.value = str(node.pk)
    browser.load_button.click()
    assert browser.info.value == ""
    assert browser.results.value.uuid == node.uuid


@pytest.mark.usefixtures("aiida_profile_clean")
@pytest.mark.parametrize("node_class", ["StructureData", "CifData"])
@pytest.mark.parametrize("replacement", ["edit", "smiles", "appearance"])
def test_explicit_reload_restores_source_history_and_representations(
    node_class, replacement
):
    source = make_source(node_class)
    browser = awb.StructureBrowserWidget()
    smiles = awb.SmilesWidget()
    manager = awb.StructureManagerWidget(
        importers=[browser, smiles], node_class=node_class
    )
    load(browser, source)
    original = manager.structure.copy()

    # Saving without Apply must be honoured on the subsequent explicit reload.
    manager.viewer._all_representations[0].color.value = "green"
    manager.viewer.btn_store_representations.click()
    saved = source.base.extras.get(awb.viewers.VIEWER_REPRESENTATIONS_EXTRA)
    assert "green" in next(iter(saved))
    attributes = source.base.attributes.all
    extras = source.base.extras.all
    count = orm.QueryBuilder().append(orm.Node).count()

    if replacement == "edit":
        edited = manager.structure.copy()
        edited.positions[1, 2] += 0.4
        manager.structure = edited
        assert len(manager.history) == 2
        assert not manager.structure_node.is_stored
    elif replacement == "smiles":
        smiles.smiles.value = "C"
        smiles.create_structure_btn.click()
        assert len(manager.structure) == 5
        assert not manager.structure_node.is_stored

    # The database selection has not changed, even after another importer runs.
    assert browser.results.value.uuid == source.uuid
    manager.viewer._all_representations[0].color.value = "red"
    load(browser, source)

    assert manager.input_structure.uuid == source.uuid
    assert manager.structure_node.uuid == source.uuid
    assert manager.viewer.structure_node.uuid == source.uuid
    assert manager.structure_node.is_stored
    assert manager.btn_store.disabled
    assert manager.structure_label.disabled
    assert manager.structure_label.value == source.label
    assert manager.structure_description.value == source.description
    assert manager.viewer.btn_store_representations.disabled is False
    np.testing.assert_allclose(manager.structure.positions, original.positions)
    np.testing.assert_allclose(manager.structure.cell, original.cell)
    np.testing.assert_array_equal(manager.structure.numbers, original.numbers)
    np.testing.assert_array_equal(manager.structure.pbc, original.pbc)
    assert len(manager.history) == 1
    representations = manager.viewer._all_representations
    assert len(representations) == 1
    assert representations[0].color.value == "green"
    assert representations[0].type.value == "ballstick"
    assert representations[0].size.value == 3
    assert representations[0].selection.value == "1..2"

    # Reload creates no provenance nodes and does not rewrite the stored source.
    assert orm.load_node(source.uuid).base.attributes.all == attributes
    assert orm.load_node(source.uuid).base.extras.all == extras
    assert orm.QueryBuilder().append(orm.Node).count() == count

    # Discarded edits or SMILES replacements must not reappear through Undo.
    manager.undo()
    assert manager.structure is None
    assert manager.input_structure is None
    assert not manager.history


@pytest.mark.usefixtures("aiida_profile_clean")
def test_reload_switches_sources_without_style_bleed_and_rejects_invalid_pk():
    source = make_source("StructureData")
    bare = orm.StructureData(ase=ase.Atoms("He", cell=[12] * 3)).store()
    browser = awb.StructureBrowserWidget()
    manager = awb.StructureManagerWidget(importers=[browser])
    load(browser, source)
    load(browser, bare)
    assert manager.structure_node.uuid == bare.uuid
    assert len(manager.history) == 1
    assert manager.viewer._all_representations[0].color.value == "element"
    load(browser, source)
    assert manager.viewer._all_representations[0].color.value == "blue"

    for pk in ["bad", "0", str(orm.Int(1).store().pk)]:
        browser.pk_input.value = pk
        browser.load_button.click()
        assert browser.info.value
        assert browser.structure is None
        assert manager.structure is None
        assert manager.structure_node is None
        assert manager.btn_store.disabled
        load(browser, source)

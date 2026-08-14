"""Check that bottom nodes are the last element in their main chain.

We enforce strict validation of the top/bottom requirements and include a
performance test for large linear chains that scales via DATASET_SIZE.
"""

import logging
import time
import tqdm
from ..chain_manager import ChainManager

logger = logging.getLogger(__name__)

# Change this variable to test the 30-second time limit on large chains.
# Set to 1000 by default. To stress test performance limits, try 10000 or 35000.
DATASET_SIZE = 1000


def _build_manager(
    comparisons: list[dict],
    all_filenames: set[str] | None = None,
) -> ChainManager:
    cm = ChainManager()
    cm.build(comparisons, all_filenames=all_filenames)
    return cm


def test_bottom_nodes_are_chain_last() -> None:
    """Strictly assert that chains always start at tops and end at bottoms."""
    logger.debug("Starting test_bottom_nodes_are_chain_last...")

    images = ["a", "b", "c", "d"]
    comparisons = [
        {"filename_a": "a", "filename_b": "b", "winner": "a"},
        {"filename_a": "b", "filename_b": "c", "winner": "b"},
        {"filename_a": "c", "filename_b": "d", "winner": "c"},
    ]

    cm = _build_manager(comparisons, all_filenames=set(images))
    tops = set(cm.get_top_nodes())
    bottoms = set(cm.get_bottom_nodes())

    bad = 0
    total = 0
    for chain in cm.get_chains().values():
        if not chain:
            continue
        total += 1
        first = chain[0]
        last = chain[-1]

        if first not in tops:
            logger.error(f"Chain ends at {first} which is NOT a top node.")
            bad += 1
        if last not in bottoms:
            logger.error(f"Chain ends at {last} which is NOT a bottom node.")
            bad += 1

    assert bad == 0, f"{bad}/{total} chains do not start/end at the absolute extremes!"


def test_performance_on_large_chains() -> None:
    """Test that ChainManager processes a large dataset under 30 seconds."""
    logger.debug("Starting test_performance_on_large_chains...")
    cm = ChainManager()

    all_real_comparisons = [
        {"filename_a": f"img_{i}", "filename_b": f"img_{i + 1}", "winner": f"img_{i}"}
        for i in range(DATASET_SIZE)
    ]

    comparisons = []
    with tqdm.tqdm(
        all_real_comparisons, desc="TEST: Filtering comparisons", delay=3.0
    ) as pbar:
        for c in pbar:
            comparisons.append(c)
    logger.debug(f"Filtered down to {len(comparisons)} comparisons.")

    start_time = time.perf_counter()
    cm.build(comparisons)
    end_time = time.perf_counter()

    elapsed = end_time - start_time
    logger.info(
        f"ChainManager.build processed {len(comparisons)} comparisons in {elapsed:.4f} seconds."
    )

    # Requirement 3: Must never take longer than 30 seconds
    assert (
        elapsed < 30.0
    ), f"Processing took {elapsed:.2f}s, which exceeds the 30s limit!"


def test_cycles_do_not_prevent_bottom_reachability() -> None:
    """Test that cyclic paths still properly reach and end at the absolute bottom."""
    logger.debug("Starting test_cycles_do_not_prevent_bottom_reachability...")
    cm = ChainManager()

    comparisons = [
        {"filename_a": "a", "filename_b": "b", "winner": "a"},
        {"filename_a": "b", "filename_b": "c", "winner": "b"},
        {"filename_a": "c", "filename_b": "a", "winner": "c"},  # cycle a>b>c>a
        {
            "filename_a": "a",
            "filename_b": "d",
            "winner": "a",
        },  # branch to absolute bottom d
    ]

    cm.build(comparisons)

    chains = cm.get_chains()
    for chain_id, chain in chains.items():
        # Every chain built MUST end at 'd', because 'd' is the only absolute bottom!
        assert (
            chain[-1] == "d"
        ), f"Chain {chain} ends at {chain[-1]} instead of the absolute bottom 'd'"


def test_transitive_reduction_sorting() -> None:
    """Test that a>b, b>c, a>c correctly builds a single sorted chain a>b>c."""
    logger.debug("Starting test_transitive_reduction_sorting...")
    cm = ChainManager()

    comparisons = [
        {"filename_a": "a", "filename_b": "b", "winner": "a"},
        {"filename_a": "b", "filename_b": "c", "winner": "b"},
        {"filename_a": "a", "filename_b": "c", "winner": "a"},  # Transitive edge
    ]

    cm.build(comparisons)
    chains = cm.get_chains()

    # Requirement 2: should return just 1 main chain a>b>c
    assert len(chains) == 1, f"Expected 1 chain, got {len(chains)}"
    main_chain = list(chains.values())[0]
    assert main_chain == ["a", "b", "c"], f"Expected ['a', 'b', 'c'], got {main_chain}"


def test_uncompared_nodes_are_isolated_top_bottom() -> None:
    """Test that uncompared images form single-node chains acting as both top and bottom."""
    logger.debug("Starting test_uncompared_nodes_are_isolated_top_bottom...")
    cm = ChainManager()

    comparisons = [
        {"filename_a": "a", "filename_b": "b", "winner": "a"},
    ]
    all_filenames = {"a", "b", "isolated_1", "isolated_2"}

    cm.build(comparisons, all_filenames=all_filenames)

    # Requirement 4: Tops and bottoms behave properly for isolated nodes
    tops = cm.get_top_nodes()
    bottoms = cm.get_bottom_nodes()

    assert "isolated_1" in tops and "isolated_1" in bottoms
    assert "isolated_2" in tops and "isolated_2" in bottoms
    assert "a" in tops and "a" not in bottoms
    assert "b" in bottoms and "b" not in tops

    # They should form their own chains of length 1
    chains = list(cm.get_chains().values())
    assert ["isolated_1"] in chains
    assert ["isolated_2"] in chains
    assert ["a", "b"] in chains


def test_top_bottom_match_database_exactly() -> None:
    """Test that computed tops/bottoms match expected: tops only have wins, bottoms only have losses."""
    logger.debug("Starting test_top_bottom_match_database_exactly...")

    images = ["a", "b", "c", "d"]
    comparisons = [
        {"filename_a": "a", "filename_b": "b", "winner": "a"},
        {"filename_a": "b", "filename_b": "c", "winner": "b"},
        {"filename_a": "c", "filename_b": "d", "winner": "c"},
    ]

    cm = _build_manager(comparisons, all_filenames=set(images))

    cm_tops = set(cm.get_top_nodes())
    cm_bottoms = set(cm.get_bottom_nodes())

    assert cm_tops == {"a"}, f"Expected only 'a' as top, got {cm_tops}"
    assert cm_bottoms == {"d"}, f"Expected only 'd' as bottom, got {cm_bottoms}"


def test_chain_snapshot_matches_known_optimal() -> None:
    """Design a DAG with unambiguous optimal chains and assert exact output."""
    comparisons = [
        # Independent chain of 4: a1 > a2 > a3 > a4
        {"filename_a": "a1", "filename_b": "a2", "winner": "a1"},
        {"filename_a": "a2", "filename_b": "a3", "winner": "a2"},
        {"filename_a": "a3", "filename_b": "a4", "winner": "a3"},
        # Independent chain of 3: b1 > b2 > b3
        {"filename_a": "b1", "filename_b": "b2", "winner": "b1"},
        {"filename_a": "b2", "filename_b": "b3", "winner": "b2"},
    ]

    cm = ChainManager()
    cm.build(comparisons)

    # The current algorithm merges upward and downward chains, so every
    # node on a chain gets the full path from top to bottom.
    assert cm.get_node_main_chain("a1")[1] == ["a1", "a2", "a3", "a4"]
    assert cm.get_node_main_chain("a2")[1] == ["a1", "a2", "a3", "a4"]
    assert cm.get_node_main_chain("a3")[1] == ["a1", "a2", "a3", "a4"]
    assert cm.get_node_main_chain("a4")[1] == ["a1", "a2", "a3", "a4"]

    assert cm.get_node_main_chain("b1")[1] == ["b1", "b2", "b3"]
    assert cm.get_node_main_chain("b2")[1] == ["b1", "b2", "b3"]
    assert cm.get_node_main_chain("b3")[1] == ["b1", "b2", "b3"]

    # Exactly 2 unique chains
    chain_tuples = {tuple(c) for c in cm.get_chains().values()}
    assert chain_tuples == {("a1", "a2", "a3", "a4"), ("b1", "b2", "b3")}

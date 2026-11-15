# Ongoing Work

## Chain Opponent Optimization

**Status:** Complete

The branch-probe experiment ended: the reusable compatible-opponent helper
(`get_branch_chain_compatible_nodes`) and the test-labeled Branch Probe phase
were removed. The production chain policy was replaced by the median-loop
`chain_middle` phase and the small-chain settler `chain_small` phase, both
driven by per-node transitive better/worse reach counts owned by
`ChainManager`; see `FUNCTION_INDEX.md` for current behavior.

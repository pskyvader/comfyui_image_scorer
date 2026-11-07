# Ongoing Work

## Chain Opponent Optimization

**Status:** Ongoing

Develop and evaluate branch-aware opponent selection to make comparisons more
likely to consolidate chain paths and grow long main chains while using as few
comparisons as practical.

The current experiment adds a reusable compatible-opponent helper and a
test-labeled Branch Probe phase immediately after Anchor Insert. The probe
chooses a random anchor, finds the anchor's immediate upper node, follows that
node's distinct main chain, and considers only candidate nodes below it. It
then removes already-compared pairs and selects the closest score pair within
the sigma range. If no compatible opponents remain, it returns no pair.

Evaluate the probe on representative graph histories before changing the
production Chain Middle policy. Track comparison count, chain count, largest
main-chain membership, and score informativeness. Keep Chain Merge out of this
experiment unless its scope is explicitly revisited.

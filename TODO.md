# modifications

## comparison section

1. when skipping an image (via either skip button, or undo button):
    current behavior: add one of the images to cache again, so it "desincronizes" the pair.
    wanted behavior: add one to cache again, and remove the other from the cache, therefore ensuring that one of the images can be selected immediately
2. numbers for phases:
    current: manual, example: "phase_label": "Phase 4 / Only Winners"
    wanted: automatic, "phase_label": "Only Winners", and in front calculate and prepend the "phase n" to the text
3. colors for phase:
    current: manual colors, example: "color": "#4ade80"
    wanted: automatic color, ranging from red to violet, in rainbow order considering the number of phases, and balanced colors.
    for example:
        if theres only 1 phase: red.
        if there are 2 phases: red, violet.
        3 phases: red, green, violet.
4. undo button:
    current: located (mobile) center right side, blocking some texts
    wanted: either make it thinner, so it botters less. or change its shape or location, maybe to center left, but that could block other texts or images. consider the alternatives before modifying anything.

## gallery section

1. search:
    current: search database prompts, options to find all or any of the comma separated terms
    wanted: advanced search, using the existing data structure for prompt tags (may require modifying the database to add said structure). add options to search by prompt (autocomplete), models and loras (dropdown), in a list of independent terms where i can also give minimum and maximum weights. example:
        input1: person, min weight:0.9, max weight: 1.1
        input2: model1,---
        input3: forest, min weight:1.0, max weight: 1.0
        input4: model2,---
        + (button to add more inputs)
    the option selector would dissapear, being replaced for the option to use AND, OR in between prompt inputs (model or loras would always be model1 OR model2 OR model...)
    another option, add multiple choice selector for loras and models, then thered be only 1 input for those, and then there should be possible to use only 1 input text to define (prompt1:weightmin-max) OR (prompt2) AND prompt3, prompt4. analyze option and propose solutions.

## maps section

1. visualisation:
    current: just doesnt work
    wanted: completely new section, with a 2d or 3d web engine that allows:
        - different circle or sphere sizes (nodes)
        - different lines thickness and lengths (links)
        - visibility control depending on distance and/or sizes, example: if a node is under a threshold, make it invisible, if a link is longer than a thershold make it invisible.
        - ability to spawn/despawn more cirle and lines on demand.
        - physics: gravity (float,sink), collisions, tension and elasticity, rigidity.
        - camera controls: zoom, pan, center, reset to default point.
        - optional: being able to use gpu for better performance

    for the simulation itself i need:
        - being able to control node base size, size multiplier based on score and number of links.
        - control gravity force, collisions toggle, map scale (area per node)
        - making sure the nodes bounce when colliding with border of the map (when collisions enabled)
        - control link base length, length multiplier based on score difference.
        - control rigidity, so a rigidity of 1.0 or 100% would never change its length, and a 0% would never try to go back to its original length
        - control visibility, with toggles and opacity.
        - separate different types of links: main links: links whose nodes both belong to the same main chain as the link, secondary: where one of the nodes belong to the same main node as the link, extra or optional: any other link. for each type have independent visibility and rigidity controls.
        - highlight main chain links and nodes when click on node.

    for controls:
        - show or hide nodes based on properties (if nodes are top/bottom/middle)
        - show or hide nodes based on score, or score range. only show when score in range, only hide when score in range
        - show or hide nodes based on number of links
        - play/pause simulation
        - performance controls (forces per tick, tick frequency)

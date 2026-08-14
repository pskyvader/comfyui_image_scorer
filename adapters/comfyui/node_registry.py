from .nodes.aesthetic_score import AestheticScoreNode

NODE_CLASS_MAPPINGS: dict[str, type] = {
    "AestheticScore": AestheticScoreNode,
}
NODE_DISPLAY_NAME_MAPPINGS: dict[str, str] = {
    "AestheticScore": "Aesthetic Score",
}

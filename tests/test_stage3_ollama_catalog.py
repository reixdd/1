from jarvis.ollama import OllamaCatalog
from jarvis.config import Settings
from jarvis.metrics import Metrics
from jarvis.capabilities import Capability, CapabilityRegistry


def test_ollama_model_selection_uses_actual_inventory(tmp_path):
    settings = Settings.from_env()
    registry = CapabilityRegistry()
    registry.register(Capability("agents.ollama.local_models", "AGENTS", "Ollama"))
    cat = OllamaCatalog(settings, Metrics(), registry)
    cat.models = [
        {"name":"embed:small","parameter_billions":0.6,"size":1},
        {"name":"qwen-fast:4b","parameter_billions":4.0,"size":4},
        {"name":"qwen-deep:27b","parameter_billions":27.0,"size":27},
    ]
    selected = cat.selection()
    assert selected == {"fast":"qwen-fast:4b","deep":"qwen-deep:27b"}

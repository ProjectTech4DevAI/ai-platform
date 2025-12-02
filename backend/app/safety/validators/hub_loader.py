import importlib
import subprocess

# Map type → Hub URI
HUB_VALIDATORS = {
    "ban_list": "hub://guardrails/ban_list",
    # Add more hub validators here in the future
}

def is_importable(module_path: str) -> bool:
    try:
        importlib.import_module(module_path)
        return True
    except ImportError:
        return False


def install_hub_validator(hub_uri: str):
    """Install a Hub validator using Guardrails CLI."""
    print(f"Installing Hub validator: {hub_uri}")
    subprocess.check_call(["guardrails", "hub", "install", hub_uri])


def load_hub_validator_class(v_type: str):
    """
    Import the validator class AFTER installation.
    """
    class_name = "".join(part.capitalize() for part in v_type.split("_"))

    module = importlib.import_module("guardrails.hub")
    return getattr(module, class_name)



def ensure_hub_validator_installed(v_type: str):
    """Install validator only if missing."""
    if v_type not in HUB_VALIDATORS:
        return

    module_path = f"guardrails.hub.{v_type}"
    if not is_importable(module_path):
        install_hub_validator(HUB_VALIDATORS[v_type])

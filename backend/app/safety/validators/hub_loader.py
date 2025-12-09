import importlib
import subprocess

# Map type → Hub URI
HUB_VALIDATORS = {
    "ban_list": "hub://guardrails/ban_list",
    # Add more hub validators here in the future
}

def is_importable(module_path: str) -> bool:
    """
    Check whether a module identified by its dotted path can be imported.
    
    Parameters:
        module_path (str): Dotted module path (e.g., 'package.module') to test.
    
    Returns:
        bool: `True` if the module can be imported, `False` otherwise.
    """
    try:
        importlib.import_module(module_path)
        return True
    except ImportError:
        return False


def install_hub_validator(hub_uri: str):
    """
    Install a Hub validator via the Guardrails CLI.
    
    Parameters:
    	hub_uri (str): Hub URI of the validator to install (e.g., "hub://guardrails/ban_list").
    
    Raises:
    	subprocess.CalledProcessError: If the Guardrails CLI returns a non-zero exit status.
    	FileNotFoundError: If the Guardrails CLI executable is not found.
    """
    print(f"Installing Hub validator: {hub_uri}")
    subprocess.check_call(["guardrails", "hub", "install", hub_uri])


def load_hub_validator_class(v_type: str):
    """
    Load a Hub validator class by its validator type name.
    
    Parameters:
        v_type (str): Validator type identifier (e.g., "ban_list"). The type is mapped to a class name by capitalizing each underscore-separated segment (e.g., "ban_list" -> "BanList").
    
    Returns:
        type: The validator class object corresponding to the given `v_type`.
    """
    class_name = "".join(part.capitalize() for part in v_type.split("_"))

    module = importlib.import_module("guardrails.hub")
    return getattr(module, class_name)



def ensure_hub_validator_installed(v_type: str):
    """
    Ensure a Hub validator for the given validator type is installed if it is available but not already importable.
    
    If `v_type` is present in HUB_VALIDATORS and the module `guardrails.hub.{v_type}` cannot be imported, this function installs the validator via the Guardrails hub. Does nothing for unrecognized validator types or when the module is already importable.
    
    Parameters:
        v_type (str): Validator type key as used in HUB_VALIDATORS (e.g., "ban_list").
    """
    if v_type not in HUB_VALIDATORS:
        return

    module_path = f"guardrails.hub.{v_type}"
    if not is_importable(module_path):
        install_hub_validator(HUB_VALIDATORS[v_type])
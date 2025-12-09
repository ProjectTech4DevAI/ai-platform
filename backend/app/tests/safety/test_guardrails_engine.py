import json
from app.safety.guardrails_engine import GuardrailsEngine
from app.safety.guardrail_config import GuardrailConfigRoot


def test_guard_creation_with_input_guard():
    guardrail_config_string = '''
    {
        "guardrails":{
            "input":[
                {
                    "type": "uli_slur_match",
                    "severity": "all",
                    "languages": [
                        "en",
                        "hi"
                    ]
                }
            ],
            "output": []
        }
    }
    '''
    guardrail_config_dict = json.loads(guardrail_config_string)
    guardrail_config = GuardrailConfigRoot(**guardrail_config_dict)
    guardrail = GuardrailsEngine(guardrail_config)

    slur_a = "बदसूरत"
    slur_b = "bhenchod"
    unsafe_input = f"You are such an {slur_a} and {slur_b}"

    safe_input = guardrail.run_input_validators(unsafe_input)

    assert slur_a not in safe_input.validated_output
    assert slur_b not in safe_input.validated_output
    assert safe_input.validated_output == "you are such an [REDACTED_SLUR] and [REDACTED_SLUR]"


def test_guard_creation_with_output_guard():
    guardrail_config_string = '''
    {
        "guardrails":{
            "input":[],
            "output": [
                {
                    "type": "uli_slur_match",
                    "severity": "all",
                    "languages": [
                        "en",
                        "hi"
                    ]
                }
            ]
        }
    }
    '''
    guardrail_config_dict = json.loads(guardrail_config_string)
    guardrail_config = GuardrailConfigRoot(**guardrail_config_dict)
    guardrail = GuardrailsEngine(guardrail_config)

    slur_a = "बदसूरत"
    slur_b = "bhenchod"
    unsafe_output = f"You are such an {slur_a} and {slur_b}"

    safe_output = guardrail.run_output_validators(unsafe_output)

    assert slur_a not in safe_output.validated_output
    assert slur_b not in safe_output.validated_output
    assert safe_output.validated_output == "you are such an [REDACTED_SLUR] and [REDACTED_SLUR]"

def test_guard_creation_with_banlist():
    """
    Verifies that combining a `uli_slur_match` input guard with a `ban_list` input guard redacts slurs and removes banned terms from input text.
    
    Configures an input guardrail with `uli_slur_match` (languages "en" and "hi", severity "all") and a `ban_list` containing "sex-determination" and "sonography", then runs input validation on a string containing two slurs and the banned word "sonography". Asserts that both slurs are absent from the validated output and that the final validated string equals the expected redacted form "you are such an [REDACTED_SLUR] and [REDACTED_SLUR] lets discuss s".
    """
    guardrail_config_string = '''
    {
        "guardrails":{
            "input":[
                {
                    "type": "uli_slur_match",
                    "severity": "all",
                    "languages": [
                        "en",
                        "hi"
                    ]
                },
                {
                    "type": "ban_list",
                    "banned_words": [
                        "sex-determination",
                        "sonography"
                    ]
                }
            ],
            "output": []
        }
    }
    '''
    guardrail_config_dict = json.loads(guardrail_config_string)
    guardrail_config = GuardrailConfigRoot(**guardrail_config_dict)
    guardrail = GuardrailsEngine(guardrail_config)

    slur_a = "बदसूरत"
    slur_b = "bhenchod"
    unsafe_input = f"You are such an {slur_a} and {slur_b}, let's discuss sonography."

    safe_input = guardrail.run_input_validators(unsafe_input)

    assert slur_a not in safe_input.validated_output
    assert slur_b not in safe_input.validated_output
    assert safe_input.validated_output == "you are such an [REDACTED_SLUR] and [REDACTED_SLUR] lets discuss s"


def test_guard_creation_with_piiremover():
    """
    Verifies that PII removal, slur redaction, and ban-list filtering applied in sequence produce the expected redacted input.
    
    Constructs a guardrail configuration with input validators in order: `pii_remover`, `uli_slur_match` (languages `en`, `hi`, severity `all`), and a `ban_list` containing "sex-determination" and "sonography". Runs the input validators on a string containing two slurs (one Hindi, one English) and the banned term, then asserts both slurs are removed from the validated output and the final `validated_output` equals the expected partially redacted string: "you are such an [REDACTED_SLUR] and [REDACTED_SLUR] lets discuss s".
    """
    guardrail_config_string = '''
    {
        "guardrails":{
            "input":[
                {
                    "type": "pii_remover"
                },
                {
                    "type": "uli_slur_match",
                    "severity": "all",
                    "languages": [
                        "en",
                        "hi"
                    ]
                },
                {
                    "type": "ban_list",
                    "banned_words": [
                        "sex-determination",
                        "sonography"
                    ]
                }
            ],
            "output": []
        }
    }
    '''
    guardrail_config_dict = json.loads(guardrail_config_string)
    guardrail_config = GuardrailConfigRoot(**guardrail_config_dict)
    guardrail = GuardrailsEngine(guardrail_config)

    slur_a = "बदसूरत"
    slur_b = "bhenchod"
    unsafe_input = f"You are such an {slur_a} and {slur_b}, let's discuss sonography."

    safe_input = guardrail.run_input_validators(unsafe_input)

    assert slur_a not in safe_input.validated_output
    assert slur_b not in safe_input.validated_output
    assert safe_input.validated_output == "you are such an [REDACTED_SLUR] and [REDACTED_SLUR] lets discuss s"
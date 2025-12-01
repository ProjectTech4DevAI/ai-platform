import json
from app.safety.guardrails_engine import GuardrailsEngine
from app.safety.guardrail_config import GuardrailConfigRoot


def get_test_guardrail_config():
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
    return guardrail_config

def test_framework():
    guardrail_config = get_test_guardrail_config()
    guardrail = GuardrailsEngine(guardrail_config)
    guardrail.make()
    safe_input = guardrail.run_input_validators("You are such an asshole and motherfucker")
    print(safe_input)
    assert "motherfucker" not in safe_input.validated_output
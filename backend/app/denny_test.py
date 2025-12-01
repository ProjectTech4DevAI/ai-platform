import json
from app.safety.guardrails_engine import GuardrailsEngine
from app.safety.guardrail_config import GuardrailConfigRoot


if __name__ == "__main__":
    print("in __main__")
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
    print(guardrail_config.guardrails)
    print(type(guardrail_config))

    # guardrail = Guardrail(guardrail_config)
    # safe_input = guardrail.parse_input(input)
    # safe_output = guardrail.parse_output(llm_output)

    
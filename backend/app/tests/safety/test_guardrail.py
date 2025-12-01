import json
from app.safety.guardrails import Guardrails
from app.safety.guardrail_config import GuardrailConfigRoot

def test_framework():
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
    # guardrail_config_string = '''
    # {
    #     "guardrails": "test"
    # }
    # '''
    # parse and validate string into sqlmodel class 
    guardrail_config_dict = json.loads(guardrail_config_string)
    guardrail_config = GuardrailConfigRoot(**guardrail_config_dict)

    # guardrail = Guardrails(guardrail_config)
    # guardrail = Guardrail(guardrail_config)
    # safe_input = guardrail.parse_input(input)
    # safe_output = guardrail.parse_output(llm_output)


    print(guardrail_config)
    assert 1 == 1
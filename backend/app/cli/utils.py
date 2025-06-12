import logging


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Estimate the cost of a model request based on input and output tokens.

    Args:
        model: The model name (e.g., 'gpt-4o', 'gpt-4o-mini')
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Estimated cost in USD
    """
    GPT_4o_MINI_2024_07_18_COSTING = {
        "input": 0.15,
        "cached_input": 0.075,
        "output": 0.60,
    }

    GPT_4o_2024_08_06_COSTING = {
        "input": 2.50,
        "cached_input": 1.25,
        "output": 10.00,
    }

    usd_per_1m = {
        "gpt-4o": GPT_4o_2024_08_06_COSTING,
        "gpt-4o-2024-08-06": GPT_4o_2024_08_06_COSTING,
        "gpt-4o-mini": GPT_4o_MINI_2024_07_18_COSTING,
        "gpt-4o-mini-2024-07-18": GPT_4o_MINI_2024_07_18_COSTING,
        # Extend with more models as needed: https://platform.openai.com/docs/pricing
    }

    pricing = usd_per_1m.get(model.lower())
    if not pricing:
        logging.warning(f"No pricing found for model '{model}'. Returning cost = 0.")
        return 0.0

    # We don't care about cached_input for now, this just to be mindful of upper bound cost to run benchmark
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost

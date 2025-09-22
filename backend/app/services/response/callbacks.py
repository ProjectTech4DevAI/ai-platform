from app.utils import APIResponse, send_callback


def get_additional_data(request: dict) -> dict:
    async_exclude_keys = {"assistant_id", "callback_url", "response_id", "question"}
    sync_exclude_keys = {
        "model",
        "instructions",
        "vector_store_ids",
        "max_num_results",
        "temperature",
        "response_id",
        "question",
    }
    if "assistant_id" in request:
        exclude_keys = async_exclude_keys
    else:
        exclude_keys = sync_exclude_keys
    return {k: v for k, v in request.items() if k not in exclude_keys}


def send_response_callback(
    callback_url: str,
    callback_response: APIResponse,
    request_dict: dict,
) -> None:
    """Send a standardized callback response to the provided callback URL."""

    callback_response = callback_response.model_dump()
    send_callback(
        callback_url,
        {
            "success": callback_response.get("success", False),
            "data": {
                **(callback_response.get("data") or {}),
                **get_additional_data(request_dict),
            },
            "error": callback_response.get("error"),
            "metadata": None,
        },
    )

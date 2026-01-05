import collections
import copy
import random
import statistics
from typing import Any

from fastapi.responses import JSONResponse

from .constants import PROTOCOL_INSTRUCTIONS
from .utils import (
    RESET_MARKER,
    check_validation_threshold,
    get_db_log,
    get_db_log_item,
    save_db_payload,
)


def _get_instructions(tasks_data: dict, campaign_id: str) -> str:
    """Get instructions: custom if provided, else protocol default, else empty."""
    campaign_info = tasks_data[campaign_id]["info"]
    if "instructions" in campaign_info:
        return campaign_info["instructions"]
    return PROTOCOL_INSTRUCTIONS.get(campaign_info.get("protocol", ""), "")



def _completed_response(
    tasks_data: dict,
    progress_data: dict,
    campaign_id: str,
    user_id: str,
) -> JSONResponse:
    """Build a completed response with progress, time, and token."""
    user_progress = progress_data[campaign_id][user_id]
    is_ok = check_validation_threshold(tasks_data, progress_data, campaign_id, user_id)
    token = user_progress["token_correct" if is_ok else "token_incorrect"]

    # Get instructions_goodbye from campaign info, with default value
    instructions_goodbye = tasks_data[campaign_id]["info"].get(
        "instructions_goodbye",
        "If someone asks you for a token of completion, show them: ${TOKEN}",
    )

    # Replace variables ${TOKEN} and ${USER_ID}
    instructions_goodbye = instructions_goodbye.replace("${TOKEN}", token).replace(
        "${USER_ID}", user_id
    )

    # Convert sets to lists for JSON serialization (for dynamic assignment)
    progress = user_progress["progress"]
    if progress and isinstance(progress[0], set):
        progress = [list(s) for s in progress]

    return JSONResponse(
        content={
            "status": "goodbye",
            "progress": progress,
            "time": user_progress["time"],
            "token": token,
            "instructions_goodbye": instructions_goodbye,
        },
        status_code=200,
    )


def get_next_item(
    campaign_id: str,
    user_id: str,
    tasks_data: dict,
    progress_data: dict,
) -> JSONResponse:
    """
    Get the next item for the user in the specified campaign.
    """
    assignment = tasks_data[campaign_id]["info"]["assignment"]
    if assignment == "task-based":
        return get_next_item_taskbased(campaign_id, user_id, tasks_data, progress_data)
    elif assignment == "single-stream":
        return get_next_item_singlestream(
            campaign_id, user_id, tasks_data, progress_data
        )
    elif assignment == "dynamic":
        return get_next_item_dynamic(campaign_id, user_id, tasks_data, progress_data)
    else:
        return JSONResponse(content="Unknown campaign assignment type", status_code=400)


def get_i_item(
    campaign_id: str,
    user_id: str,
    tasks_data: dict,
    progress_data: dict,
    item_i: int,
) -> JSONResponse:
    """
    Get a specific item by index for the user in the specified campaign.
    """
    assignment = tasks_data[campaign_id]["info"]["assignment"]
    if assignment == "task-based":
        return get_i_item_taskbased(
            campaign_id, user_id, tasks_data, progress_data, item_i
        )
    elif assignment == "single-stream":
        return get_i_item_singlestream(
            campaign_id, user_id, tasks_data, progress_data, item_i
        )
    else:
        return JSONResponse(
            content="Get item not supported for this assignment type", status_code=400
        )


def get_i_item_taskbased(
    campaign_id: str,
    user_id: str,
    data_all: dict,
    progress_data: dict,
    item_i: int,
) -> JSONResponse:
    """
    Get specific item for task-based protocol.
    """
    user_progress = progress_data[campaign_id][user_id]

    # try to get existing annotations if any
    items_existing = get_db_log_item(campaign_id, user_id, item_i)
    payload_existing = None
    if items_existing:
        # get the latest ones
        latest_item = items_existing[-1]
        payload_existing = {"annotation": latest_item["annotation"]}
        if "comment" in latest_item:
            payload_existing["comment"] = latest_item["comment"]

    if item_i < 0 or item_i >= len(data_all[campaign_id]["data"][user_id]):
        return JSONResponse(content="Item index out of range", status_code=400)

    return JSONResponse(
        content={
            "status": "ok",
            "progress": user_progress["progress"],
            "time": user_progress["time"],
            "info": {
                "item_i": item_i,
                "instructions": _get_instructions(data_all, campaign_id),
            }
            | {
                k: v
                for k, v in data_all[campaign_id]["info"].items()
                if k in {"protocol", "sliders"}
            },
            "payload": data_all[campaign_id]["data"][user_id][item_i],
        }
        | ({"payload_existing": payload_existing} if payload_existing else {}),
        status_code=200,
    )


def get_i_item_singlestream(
    campaign_id: str,
    user_id: str,
    data_all: dict,
    progress_data: dict,
    item_i: int,
) -> JSONResponse:
    """
    Get specific item for single-stream assignment.
    """
    user_progress = progress_data[campaign_id][user_id]

    # try to get existing annotations if any
    # note the None user_id since it is shared
    items_existing = get_db_log_item(campaign_id, None, item_i)
    payload_existing = None
    if items_existing:
        # get the latest ones
        latest_item = items_existing[-1]
        payload_existing = {"annotation": latest_item["annotation"]}
        if "comment" in latest_item:
            payload_existing["comment"] = latest_item["comment"]

    if item_i < 0 or item_i >= len(data_all[campaign_id]["data"]):
        return JSONResponse(content="Item index out of range", status_code=400)

    return JSONResponse(
        content={
            "status": "ok",
            "progress": user_progress["progress"],
            "time": user_progress["time"],
            "info": {
                "item_i": item_i,
                "instructions": _get_instructions(data_all, campaign_id),
            }
            | {
                k: v
                for k, v in data_all[campaign_id]["info"].items()
                if k in {"protocol", "sliders"}
            },
            "payload": data_all[campaign_id]["data"][item_i],
        }
        | ({"payload_existing": payload_existing} if payload_existing else {}),
        status_code=200,
    )


def get_next_item_taskbased(
    campaign_id: str,
    user_id: str,
    data_all: dict,
    progress_data: dict,
) -> JSONResponse:
    """
    Get the next item for task-based assignment.
    """
    user_progress = progress_data[campaign_id][user_id]
    if all(user_progress["progress"]):
        return _completed_response(data_all, progress_data, campaign_id, user_id)

    # find first incomplete item
    item_i = min([i for i, v in enumerate(user_progress["progress"]) if not v])

    # try to get existing annotations if any
    items_existing = get_db_log_item(campaign_id, user_id, item_i)
    payload_existing = None
    if items_existing:
        # get the latest ones
        latest_item = items_existing[-1]
        payload_existing = {"annotation": latest_item["annotation"]}
        if "comment" in latest_item:
            payload_existing["comment"] = latest_item["comment"]

    return JSONResponse(
        content={
            "status": "ok",
            "progress": user_progress["progress"],
            "time": user_progress["time"],
            "info": {
                "item_i": item_i,
                "instructions": _get_instructions(data_all, campaign_id),
            }
            | {
                k: v
                for k, v in data_all[campaign_id]["info"].items()
                if k in {"protocol", "sliders"}
            },
            "payload": data_all[campaign_id]["data"][user_id][item_i],
        }
        | ({"payload_existing": payload_existing} if payload_existing else {}),
        status_code=200,
    )


def get_next_item_singlestream(
    campaign_id: str,
    user_id: str,
    data_all: dict,
    progress_data: dict,
) -> JSONResponse:
    """
    Get the next item for single-stream assignment.
    In this mode, all users share the same pool of items.
    Items are randomly selected from unfinished items.

    Note: There is a potential race condition where multiple users could
    receive the same item simultaneously. This is fine since we store all responses.
    """
    user_progress = progress_data[campaign_id][user_id]
    progress = user_progress["progress"]

    if all(progress):
        return _completed_response(data_all, progress_data, campaign_id, user_id)

    # find a random incomplete item
    incomplete_indices = [i for i, v in enumerate(progress) if not v]
    item_i = random.choice(incomplete_indices)

    # try to get existing annotations if any
    # note the None user_id since it is shared
    items_existing = get_db_log_item(campaign_id, None, item_i)
    payload_existing = None
    if items_existing:
        # get the latest ones
        latest_item = items_existing[-1]
        payload_existing = {"annotation": latest_item["annotation"]}
        if "comment" in latest_item:
            payload_existing["comment"] = latest_item["comment"]

    return JSONResponse(
        content={
            "status": "ok",
            "time": user_progress["time"],
            "progress": progress,
            "info": {
                "item_i": item_i,
                "instructions": _get_instructions(data_all, campaign_id),
            }
            | {
                k: v
                for k, v in data_all[campaign_id]["info"].items()
                if k in {"protocol", "sliders"}
            },
            "payload": data_all[campaign_id]["data"][item_i],
        }
        | ({"payload_existing": payload_existing} if payload_existing else {}),
        status_code=200,
    )


def get_next_item_dynamic(
    campaign_id: str,
    user_id: str,
    tasks_data: dict,
    progress_data: dict,
) -> JSONResponse:
    """
    Get the next item for dynamic assignment based on model performance.

    NOTE: All items must contain all model outputs for this assignment type to work.

    In this mode, items are selected based on the current performance of models:
    1. Contrastive comparison: `dynamic_contrastive_models` models are randomly selected and shown per item
    2. First phase: Each model gets `dynamic_first` annotations with fully random selection
    3. After first phase: Top `dynamic_top` models are identified, K randomly selected from them
    4. Items with least annotations for the selected models are prioritized
    5. With probability `dynamic_backoff`, uniformly random selection is used instead
    """
    import random

    user_progress = progress_data[campaign_id][user_id]
    campaign_data = tasks_data[campaign_id]

    # Get all unique models in the campaign (all items must have all models)
    all_models = list(set(campaign_data["data"][0][0]["tgt"].keys()))

    # Check if completed (all models completed for all items)
    # NOTE: this will rarely trigger but we don't have a good way to know when to end anyway for now
    if all(len(v) == len(all_models) for v in user_progress["progress"]):
        return _completed_response(tasks_data, progress_data, campaign_id, user_id)

    # Get configuration parameters
    dynamic_top = campaign_data["info"].get("dynamic_top", 2)
    dynamic_first = campaign_data["info"].get("dynamic_first", 5)
    dynamic_contrastive_models = campaign_data["info"].get(
        "dynamic_contrastive_models", 1
    )
    dynamic_backoff = campaign_data["info"].get("dynamic_backoff", 0)

    # Count annotations per (model, item) pair to track coverage
    annotations = get_db_log(campaign_id)
    model_item_counts = collections.defaultdict(int)  # (model, item_i) -> count
    model_total_counts = collections.defaultdict(int)  # model -> total count

    for annotation_line in annotations:
        if (item_i := annotation_line.get("item_i")) is not None:
            # Count which models were annotated in this annotation
            for annotation_item in annotation_line.get("annotation", []):
                for model in annotation_item:
                    model_item_counts[(model, item_i)] += 1
                    model_total_counts[model] += 1

    # Check if we're still in the first phase (collecting initial data)
    in_first_phase = any(
        model_total_counts.get(model, 0) < dynamic_first for model in all_models
    )

    # Select which models to show
    if in_first_phase:
        # First phase or backoff: select models that don't have enough annotations yet
        selected_models = random.sample(
            [
                model
                for model in all_models
                if model_total_counts.get(model, 0) < dynamic_first
            ],
            k=min(dynamic_contrastive_models, len(all_models)),
        )
    elif random.random() < dynamic_backoff:
        # Backoff: select K models randomly from all models
        selected_models = random.sample(
            all_models, k=min(dynamic_contrastive_models, len(all_models))
        )
    else:
        # Calculate model scores from annotations
        model_scores = collections.defaultdict(list)
        for annotation_line in annotations:
            for annotation_item in annotation_line.get("annotation", {}):
                for model in annotation_item:
                    if "score" in annotation_item[model]:
                        model_scores[model].append(annotation_item[model]["score"])

        # Calculate average scores
        model_avg_scores = {
            model: statistics.mean(scores) for model, scores in model_scores.items()
        }

        # Get top N models
        sorted_models = sorted(
            model_avg_scores.items(), key=lambda x: x[1], reverse=True
        )
        top_models = [model for model, score in sorted_models[:dynamic_top]]

        # From top N, randomly select K models
        selected_models = random.sample(
            top_models, k=min(dynamic_contrastive_models, len(top_models))
        )

    # Find incomplete items for the selected models (items where not all selected models are done)
    item_annotation_counts = {
        i: sum(model in completed_models for model in selected_models)
        for i, completed_models in enumerate(user_progress["progress"])
    }

    # Select item with minimum annotations (with random tiebreaking)
    min_annotations = min(item_annotation_counts.values())
    items_with_min = [
        item_i
        for item_i, count in item_annotation_counts.items()
        if count == min_annotations
    ]
    item_i = random.choice(items_with_min)

    # Prune the payload to only include selected models
    original_item = campaign_data["data"][item_i]
    pruned_item = []
    for doc_segment in original_item:
        pruned_segment = doc_segment.copy()
        # Filter tgt to only include selected models
        pruned_segment["tgt"] = {
            model: doc_segment["tgt"][model]
            for model in selected_models
            if model in doc_segment["tgt"]
        }
        # Also filter error_spans if present
        if "error_spans" in doc_segment:
            pruned_segment["error_spans"] = {
                model: doc_segment["error_spans"][model]
                for model in selected_models
                if model in doc_segment.get("error_spans", {})
            }
        # Also filter validation if present
        if "validation" in doc_segment:
            pruned_segment["validation"] = {
                model: doc_segment["validation"][model]
                for model in selected_models
                if model in doc_segment.get("validation", {})
            }
        pruned_item.append(pruned_segment)

    return JSONResponse(
        content={
            "status": "ok",
            "time": user_progress["time"],
            "progress": user_progress["progress"],
            "info": {
                "item_i": item_i,
                "instructions": _get_instructions(tasks_data, campaign_id),
            }
            | {
                k: v
                for k, v in campaign_data["info"].items()
                if k in {"protocol", "sliders"}
            },
            "payload": pruned_item,
        },
        status_code=200,
    )


def _reset_user_time(progress_data: dict, campaign_id: str, user_id: str) -> None:
    """Reset time tracking fields for a user."""
    progress_data[campaign_id][user_id]["time"] = 0.0
    progress_data[campaign_id][user_id]["time_start"] = None
    progress_data[campaign_id][user_id]["time_end"] = None
    progress_data[campaign_id][user_id]["validations"] = {}


def _get_user_annotated_items(campaign_id: str, user_id: str) -> set[int]:
    """
    Get the set of item indices that a specific user has annotated.
    
    Args:
        campaign_id: The campaign identifier
        user_id: The user identifier
        
    Returns:
        Set of item indices (item_i) that the user has annotated
    """
    log = get_db_log(campaign_id)
    user_items = set()
    for entry in log:
        if entry.get("user_id") == user_id and entry.get("annotation") != RESET_MARKER:
            if (item_i := entry.get("item_i")) is not None:
                user_items.add(item_i)
    return user_items


def reset_task(
    campaign_id: str,
    user_id: str,
    tasks_data: dict,
    progress_data: dict,
) -> JSONResponse:
    """
    Reset the task progress for the user in the specified campaign.
    Saves a reset marker to mask existing annotations.
    """
    assignment = tasks_data[campaign_id]["info"]["assignment"]
    if assignment == "task-based":
        # Save reset marker for this user to mask existing annotations
        num_items = len(tasks_data[campaign_id]["data"][user_id])
        for item_i in range(num_items):
            save_db_payload(
                campaign_id,
                {"user_id": user_id, "item_i": item_i, "annotation": RESET_MARKER},
            )
        progress_data[campaign_id][user_id]["progress"] = [False] * num_items
        _reset_user_time(progress_data, campaign_id, user_id)
        return JSONResponse(content="ok", status_code=200)
    elif assignment == "single-stream":
        # Find all items that this user has annotated
        user_items = _get_user_annotated_items(campaign_id, user_id)
        
        # Save reset markers only for items this user has touched
        for item_i in user_items:
            save_db_payload(
                campaign_id,
                {"user_id": user_id, "item_i": item_i, "annotation": RESET_MARKER},
            )
        
        # Reset only the touched items in all users' progress (shared pool)
        for uid in progress_data[campaign_id]:
            for item_i in user_items:
                progress_data[campaign_id][uid]["progress"][item_i] = False
        
        # Reset only the specified user's time
        _reset_user_time(progress_data, campaign_id, user_id)
        return JSONResponse(content="ok", status_code=200)
    elif assignment == "dynamic":
        # Find all items that this user has annotated
        user_items = _get_user_annotated_items(campaign_id, user_id)
        
        # Save reset markers only for items this user has touched
        for item_i in user_items:
            save_db_payload(
                campaign_id,
                {"user_id": user_id, "item_i": item_i, "annotation": RESET_MARKER},
            )

        progress_data_user = copy.deepcopy(progress_data[campaign_id][user_id]["progress"])
        
        # Reset only the touched items in all users' progress (shared pool, use lists to track models)
        for uid in progress_data[campaign_id]:
            for item_i in user_items:
                progress_data[campaign_id][uid]["progress"][item_i] = [
                    x for x in progress_data[campaign_id][uid]["progress"][item_i]
                    if x not in progress_data_user[item_i]
                ]
        
        # Reset only the specified user's time
        _reset_user_time(progress_data, campaign_id, user_id)
        return JSONResponse(content="ok", status_code=200)
    else:
        return JSONResponse(
            content="Reset not supported for this assignment type", status_code=400
        )


def update_progress(
    campaign_id: str,
    user_id: str,
    tasks_data: dict,
    progress_data: dict,
    item_i: int,
    payload: Any,
) -> JSONResponse:
    """
    Log the user's response for the specified item in the campaign.
    """
    assignment = tasks_data[campaign_id]["info"]["assignment"]
    if assignment == "task-based":
        # even if it's already set it should be fine
        progress_data[campaign_id][user_id]["progress"][item_i] = True
        return JSONResponse(content={"status": "ok"}, status_code=200)
    elif assignment == "single-stream":
        # progress all users
        for uid in progress_data[campaign_id]:
            progress_data[campaign_id][uid]["progress"][item_i] = True
        return JSONResponse(content="ok", status_code=200)
    elif assignment == "dynamic":
        # For dynamic, track which models were annotated
        # Extract models from the payload annotation
        annotated_models = []
        if "annotation" in payload:
            for annotation_item in payload.get("annotation", []):
                if isinstance(annotation_item, dict):
                    annotated_models.extend(annotation_item.keys())

        # Update progress for all users (shared pool)
        for uid in progress_data[campaign_id]:
            # Add the newly annotated models
            progress_data[campaign_id][uid]["progress"][item_i].extend(annotated_models)
        return JSONResponse(content="ok", status_code=200)
    else:
        return JSONResponse(content="Unknown campaign assignment type", status_code=400)

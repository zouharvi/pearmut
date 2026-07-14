"""
Each assignment (task-based, single-stream, dynamic) has to support two main actions: getting the next item, and getting a specific item by ID.
"""

import collections
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
    is_form_document,
    save_db_payload,
    shuffled,
)

# Public campaign info fields that are sent to the client
CAMPAIGN_INFO_PUBLIC = {
    "protocol",
    "sliders",
    "textfield",
    "show_model_names",
    "show_alignment",
    "show_progress",
    "word_level",
    "mqm_categories",
    "mqm_severities",
    "slider_colors",
    "special_tokens",
}


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

    return JSONResponse(
        content={
            "status": "goodbye",
            "progress": user_progress["progress"],
            "progress_welcome": user_progress["progress_welcome"],
            "time": user_progress["time"],
            "token": token,
            "instructions_goodbye": instructions_goodbye,
        },
        status_code=200,
    )


def render_item_response(
    campaign_id: str,
    tasks_data: dict,
    user_id: str,
    user_progress: dict,
    item_i: int | str,
    payload: Any,
    fetch_existing: str | bool = "within_user",
) -> JSONResponse:
    """Helper to consistently build the JSONResponse for an item."""
    is_form = is_form_document(payload)
    
    payload_existing = None
    if fetch_existing:
        log_user_id = user_id if fetch_existing == "within_user" else None
        items_existing = get_db_log_item(campaign_id, log_user_id, item_i)
        if items_existing:
            latest_item = items_existing[-1]
            payload_existing = {"annotation": latest_item["annotation"]}
            if "comment" in latest_item:
                payload_existing["comment"] = latest_item["comment"]

    return JSONResponse(
        content={
            "status": "form" if is_form else "ok",
            "time": user_progress["time"],
            "progress": user_progress["progress"],
            "progress_welcome": user_progress["progress_welcome"],
            "info": {
                "item_i": item_i,
                "instructions": _get_instructions(tasks_data, campaign_id),
            }
            | {
                k: v
                for k, v in tasks_data[campaign_id]["info"].items()
                if k in CAMPAIGN_INFO_PUBLIC
            },
            "payload": payload,
        }
        | ({"payload_existing": payload_existing} if payload_existing else {}),
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
    user_progress = progress_data[campaign_id][user_id]
    progress_welcome = user_progress.get("progress_welcome", [])
    
    # Random check
    campaign_info = tasks_data[campaign_id]["info"]
    data_random = tasks_data[campaign_id].get("data_random")
    
    if all(progress_welcome) and data_random and random.random() < campaign_info["data_random_prob"]:
        log = get_db_log(campaign_id)
        seen_random = {
            int(entry["item_i"].split("_")[1])
            for entry in log
            if entry.get("user_id") == user_id
            and isinstance(entry.get("item_i"), str)
            and entry["item_i"].startswith("random_")
        }
        available = [i for i in range(len(data_random)) if i not in seen_random]
        if available:
            chosen_i = random.choice(available)
            item_id = f"random_{chosen_i}"
            payload = data_random[chosen_i]


            return render_item_response(
                campaign_id,
                tasks_data,
                user_id,
                user_progress,
                item_id,
                payload,
                fetch_existing=False,
            )

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
    item_i: int | str,
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
    elif assignment == "dynamic":
        return get_i_item_dynamic(
            campaign_id, user_id, tasks_data, progress_data, item_i
        )
    return JSONResponse(content="Unknown assignment type", status_code=400)


def get_i_item_taskbased(
    campaign_id: str,
    user_id: str,
    tasks_data: dict,
    progress_data: dict,
    item_i: int | str,  # Can be int or str like "welcome_0"
) -> JSONResponse:
    """
    Get specific item for task-based protocol.
    """
    user_progress = progress_data[campaign_id][user_id]
    progress_welcome = user_progress["progress_welcome"]

    # if welcome_X, payload is from data_welcome[X], otherwise data[user][X]
    if isinstance(item_i, str) and item_i.startswith("welcome_"):
        actual_index = int(item_i.split("_")[1])
        if actual_index < 0 or actual_index >= len(
            tasks_data[campaign_id]["data_welcome"]
        ):
            return JSONResponse(
                content="Welcome item index out of range", status_code=400
            )
        payload = tasks_data[campaign_id]["data_welcome"][actual_index]
    else:
        # Prevent accessing regular items unless all welcome items are complete
        if not all(progress_welcome):
            return JSONResponse(
                content="Complete all welcome items before accessing regular items",
                status_code=400,
            )
        assert isinstance(item_i, int)
        if item_i < 0 or item_i >= len(tasks_data[campaign_id]["data"][user_id]):
            return JSONResponse(content="Item index out of range", status_code=400)
        payload = tasks_data[campaign_id]["data"][user_id][item_i]

    return render_item_response(
        campaign_id,
        tasks_data,
        user_id,
        user_progress,
        item_i,
        payload,
    )


def get_i_item_singlestream(
    campaign_id: str,
    user_id: str,
    tasks_data: dict,
    progress_data: dict,
    item_i: int | str,  # Can be int or str like "welcome_0"
) -> JSONResponse:
    """
    Get specific item for single-stream assignment.
    """
    user_progress = progress_data[campaign_id][user_id]
    progress_welcome = user_progress["progress_welcome"]

    # Convert welcome_X string to integer index
    actual_index = item_i
    is_welcome_item = isinstance(item_i, str) and item_i.startswith("welcome_")
    if is_welcome_item:
        assert isinstance(item_i, str)
        actual_index = int(item_i.split("_")[1])
        # Validate against total number of welcome items
        if actual_index < 0 or actual_index >= len(progress_welcome):
            return JSONResponse(
                content="Welcome item index out of range", status_code=400
            )
        payload = tasks_data[campaign_id]["data_welcome"][actual_index]
    else:
        # Prevent accessing regular items unless all welcome items are complete
        if not all(progress_welcome):
            return JSONResponse(
                content="Complete all welcome items before accessing regular items",
                status_code=400,
            )
        payload = tasks_data[campaign_id]["data"][actual_index]

    assert isinstance(actual_index, int)
    if actual_index < 0 or actual_index >= len(tasks_data[campaign_id]["data"]):
        return JSONResponse(content="Item index out of range", status_code=400)

    return render_item_response(
        campaign_id,
        tasks_data,
        user_id,
        user_progress,
        item_i,
        payload,
        fetch_existing="within_user" if is_welcome_item else "across_all",
    )


def get_next_item_taskbased(
    campaign_id: str,
    user_id: str,
    tasks_data: dict,
    progress_data: dict,
) -> JSONResponse:
    """
    Get the next item for task-based assignment.
    """
    user_progress = progress_data[campaign_id][user_id]
    progress_welcome = user_progress["progress_welcome"]

    # Check if there are incomplete welcome items first
    if not all(progress_welcome):
        # Find first incomplete welcome item
        item_i = next(i for i, v in enumerate(progress_welcome) if not v)
        item_id = f"welcome_{item_i}"

        payload = tasks_data[campaign_id]["data_welcome"][item_i]

        return render_item_response(
            campaign_id,
            tasks_data,
            user_id,
            user_progress,
            item_id,
            payload,
        )

    # All welcome items complete, proceed with regular items
    if all(v == "completed" for v in user_progress["progress"]):
        return _completed_response(tasks_data, progress_data, campaign_id, user_id)

    # find first incomplete item
    item_i = min(
        [i for i, v in enumerate(user_progress["progress"]) if v != "completed"]
    )

    payload = tasks_data[campaign_id]["data"][user_id][item_i]

    return render_item_response(
        campaign_id,
        tasks_data,
        user_id,
        user_progress,
        item_i,
        payload,
    )


def get_next_item_singlestream(
    campaign_id: str,
    user_id: str,
    tasks_data: dict,
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
    progress_welcome = user_progress["progress_welcome"]

    # Check if there are incomplete welcome items first - must complete all before proceeding
    if not all(progress_welcome):
        # Find first incomplete welcome item (sequential, not random)
        item_i = next(i for i, v in enumerate(progress_welcome) if not v)
        item_id = f"welcome_{item_i}"

        payload = tasks_data[campaign_id]["data_welcome"][item_i]

        return render_item_response(
            campaign_id,
            tasks_data,
            user_id,
            user_progress,
            item_id,
            payload,
            fetch_existing="within_user",
        )

    # All welcome items complete, proceed with regular items
    # Check if user reached docs_per_user limit (if specified)
    if (
        docs_per_user := tasks_data[campaign_id]["info"].get("docs_per_user")
    ) is not None:
        completed_docs = sum(v == "completed" for v in progress if v)
        if completed_docs >= docs_per_user:
            return _completed_response(tasks_data, progress_data, campaign_id, user_id)
    elif all(v in {"completed", "completed_foreign"} for v in progress):
        return _completed_response(tasks_data, progress_data, campaign_id, user_id)

    # find a random incomplete item
    incomplete_indices = [
        i for i, v in enumerate(progress) if v not in {"completed", "completed_foreign"}
    ]
    item_i = random.choice(incomplete_indices)

    payload = tasks_data[campaign_id]["data"][item_i]

    return render_item_response(
        campaign_id,
        tasks_data,
        user_id,
        user_progress,
        item_i,
        payload,
        fetch_existing="across_all",
    )


def get_i_item_dynamic(
    campaign_id: str,
    user_id: str,
    tasks_data: dict,
    progress_data: dict,
    item_i: int | str,
) -> JSONResponse:
    """
    Get specific item for dynamic assignment.
    When navigating to a specific item, show all annotated models (from any user)
    rather than applying dynamic selection.
    """
    user_progress = progress_data[campaign_id][user_id]
    campaign_data = tasks_data[campaign_id]
    progress_welcome = user_progress["progress_welcome"]

    if isinstance(item_i, str) and item_i.startswith("welcome_"):
        actual_index = int(item_i.split("_")[1])
        if actual_index < 0 or actual_index >= len(progress_welcome):
            return JSONResponse(
                content="Welcome item index out of range", status_code=400
            )

        return render_item_response(
            campaign_id,
            tasks_data,
            user_id,
            user_progress,
            item_i,
            campaign_data["data_welcome"][actual_index],
            fetch_existing="within_user",
        )

    if not all(progress_welcome):
        return JSONResponse(
            content="Complete all welcome items before accessing regular items",
            status_code=400,
        )

    if (
        not isinstance(item_i, int)
        or item_i < 0
        or item_i >= len(campaign_data["data"])
    ):
        return JSONResponse(content="Item index out of range", status_code=400)

    # Show all models that have been annotated for this item.
    # A non-null status means the model was annotated by this user ("completed")
    # or by another user ("completed_foreign"), so this covers annotations from all users.
    item_progress = user_progress["progress"][item_i]
    annotated_models = [
        model for model, status in item_progress.items() if status is not None
    ]

    original_item = campaign_data["data"][item_i]
    if annotated_models:
        pruned_item = []
        for doc_segment in original_item:
            pruned_segment = doc_segment.copy()
            pruned_segment["tgt"] = {
                model: doc_segment["tgt"][model]
                for model in annotated_models
                if model in doc_segment["tgt"]
            }
            if "error_spans" in doc_segment:
                pruned_segment["error_spans"] = {
                    model: doc_segment["error_spans"][model]
                    for model in annotated_models
                    if model in doc_segment.get("error_spans", {})
                }
            if "validation" in doc_segment:
                pruned_segment["validation"] = {
                    model: doc_segment["validation"][model]
                    for model in annotated_models
                    if model in doc_segment.get("validation", {})
                }
            pruned_item.append(pruned_segment)
    else:
        pruned_item = original_item

    return render_item_response(
        campaign_id,
        tasks_data,
        user_id,
        user_progress,
        item_i,
        pruned_item,
        fetch_existing=True,
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
    1. Warmup phase: Each model gets `dynamic_coldstart` annotations with fully random selection
    2. Contrastive comparison: `dynamic_models` models are randomly selected and shown per itemem
    3. Items with least annotations for the selected models are prioritized
    """
    import random

    user_progress = progress_data[campaign_id][user_id]
    campaign_data = tasks_data[campaign_id]
    progress_welcome = user_progress["progress_welcome"]

    # Check if there are incomplete welcome items first - must complete all before proceeding
    if not all(progress_welcome):
        # Find first incomplete welcome item (sequential)
        item_i = next(i for i, v in enumerate(progress_welcome) if not v)
        item_id = f"welcome_{item_i}"

        return render_item_response(
            campaign_id,
            tasks_data,
            user_id,
            user_progress,
            item_id,
            campaign_data["data_welcome"][item_i],
            fetch_existing="within_user",
        )


    # Get all unique models in the campaign (all items must have all models)
    all_models = list(set(campaign_data["data"][0][0]["tgt"].keys()))

    # Check if completed
    # First check if docs_per_user limit is reached
    if (docs_per_user := campaign_data["info"].get("docs_per_user")) is not None:
        # Count specifically number of annotations across models
        completed_docs = sum(
            v == "completed" for mv in user_progress["progress"] for v in mv.values()
        )
        if completed_docs >= docs_per_user:
            return _completed_response(tasks_data, progress_data, campaign_id, user_id)
    # Otherwise check if all models completed for all items
    elif all(
        v in {"completed", "completed_foreign"}
        for mv in user_progress["progress"]
        for v in mv.values()
    ):
        return _completed_response(tasks_data, progress_data, campaign_id, user_id)

    # Get configuration parameters
    dynamic_coldstart = campaign_data["info"].get("dynamic_coldstart", 5)
    dynamic_models = campaign_data["info"].get("dynamic_models", 1)

    # Count annotations per (model, item) pair to track coverage
    annotations = get_db_log(campaign_id)
    model_item_counts = collections.defaultdict(int)  # (model, item_i) -> count
    model_total_counts = collections.defaultdict(int)  # model -> total count

    for annotation_line in annotations:
        if (item_i := annotation_line.get("item_i")) is not None:
            # Count which models were annotated in this annotation
            for annotation_item in annotation_line.get("annotation", []):
                # we don't skip empty annotations from skippable items as they won't be assigned anyway
                for model in annotation_item:
                    model_item_counts[(model, item_i)] += 1
                    model_total_counts[model] += 1

    # Check if we're still in the first phase (collecting initial data)
    in_warmup_phase = any(
        model_total_counts.get(model, 0) < dynamic_coldstart for model in all_models
    )

    # Select which models to show
    if in_warmup_phase:
        # First phase: select models that don't have enough annotations yet
        available_models = [
            model
            for model in all_models
            if model_total_counts.get(model, 0) < dynamic_coldstart
        ]
        if len(available_models) < dynamic_models:
            # If not enough models in warmup, include all models to fill the slots
            available_models += [
                model for model in shuffled(all_models) if model not in available_models
            ][: dynamic_models - len(available_models)]
        selected_models = random.sample(
            available_models,
            k=min(dynamic_models, len(available_models)),
        )
    else:
        import numpy as np

        # Calculate model scores from annotations
        model_scores = collections.defaultdict(list)
        for annotation_line in annotations:
            for annotation_item in annotation_line.get("annotation", {}):
                if annotation_item is None:  # skippable items have no annotation
                    continue
                for model in annotation_item:
                    if "score" in annotation_item[model] and annotation_item[model]["score"] is not None:
                        model_scores[model].append(annotation_item[model]["score"])

        # Calculate average scores
        model_avg_scores = {
            model: statistics.mean(model_scores[model]) if model_scores[model] else 0.0
            for model in all_models
        }
        model_weights_dict = {
            # 1/(rank + 1) to give higher weight to better performing models
            model: 1 / (rank + 1)**0.5
            for rank, model in enumerate(
                sorted(model_avg_scores.keys(), key=lambda x: model_avg_scores[x], reverse=True)
            )
        }
        model_weights_arr = np.array([model_weights_dict[model] for model in all_models], dtype=float)
        model_weights_arr /= model_weights_arr.sum()
        model_weights = model_weights_arr.tolist()
        selected_models = np.random.choice(
            all_models,
            size=min(dynamic_models, len(all_models)),
            replace=False,
            p=model_weights,
        )

    # Find incomplete items (None or completed_foreign status)
    # if any chosen model for an item is not completed, it's considered incomplete
    incomplete_indices = [
        i
        for i, mv in enumerate(user_progress["progress"])
        if all(mv[model] not in {"completed", "completed_foreign"} for model in selected_models)
    ]

    # if we dont find any incomplete items for the selected models, we can relax the condition to include items that are partially completed (some models completed, some not)
    if not incomplete_indices:
        incomplete_indices = [
            i
            for i, mv in enumerate(user_progress["progress"])
            if any(mv[model] not in {"completed", "completed_foreign"} for model in selected_models)
        ]

    # If no incomplete items, user (and everyone) is done
    if not incomplete_indices:
        return _completed_response(tasks_data, progress_data, campaign_id, user_id)

    # Select the first incomplete item
    item_i = incomplete_indices[0]

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

    return render_item_response(
        campaign_id,
        tasks_data,
        user_id,
        user_progress,
        item_i,
        pruned_item,
        fetch_existing=False,
    )


def _reset_user_time(progress_data: dict, campaign_id: str, user_id: str) -> None:
    """Reset time tracking fields for a user."""
    progress_data[campaign_id][user_id]["time"] = 0.0
    progress_data[campaign_id][user_id]["time_start"] = None
    progress_data[campaign_id][user_id]["time_end"] = None
    progress_data[campaign_id][user_id]["validations"] = {}


def _get_user_annotated_items(campaign_id: str, user_id: str) -> set[int | str]:
    """
    Get the set of item indices that a specific user has annotated.

    Args:
        campaign_id: The campaign identifier
        user_id: The user identifier

    Returns:
        Set of item indices (item_i) that the user has annotated.
        Can include both int indices for regular items and string IDs like "welcome_0" for welcome items.
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
    Only resets items originally completed by this user (not completed_foreign).
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
        progress_data[campaign_id][user_id]["progress"] = [None] * num_items
        # Reset welcome items progress if it exists
        if "progress_welcome" in progress_data[campaign_id][user_id]:
            num_welcome = len(progress_data[campaign_id][user_id]["progress_welcome"])
            progress_data[campaign_id][user_id]["progress_welcome"] = [
                False
            ] * num_welcome
            # Save reset markers for welcome items
            for i in range(num_welcome):
                save_db_payload(
                    campaign_id,
                    {
                        "user_id": user_id,
                        "item_i": f"welcome_{i}",
                        "annotation": RESET_MARKER,
                    },
                )
        _reset_user_time(progress_data, campaign_id, user_id)
        return JSONResponse(content="ok", status_code=200)
    elif assignment == "single-stream":
        # Find all items that this user has annotated (has "completed")
        user_items_to_reset = [
            i
            for i, status in enumerate(progress_data[campaign_id][user_id]["progress"])
            if status == "completed"
        ]

        # Save reset markers for all items this user has touched
        for item_i in user_items_to_reset:
            save_db_payload(
                campaign_id,
                {"user_id": user_id, "item_i": item_i, "annotation": RESET_MARKER},
            )

        # Reset the completed items in all users' progress (shared pool)
        for uid in progress_data[campaign_id]:
            for item_i in user_items_to_reset:
                progress_data[campaign_id][uid]["progress"][item_i] = None

        # Reset all welcome items progress for this user (per-user, not shared)
        if "progress_welcome" in progress_data[campaign_id][user_id]:
            # Save reset markers only for completed welcome items
            for i, status in enumerate(
                progress_data[campaign_id][user_id]["progress_welcome"]
            ):
                if status:  # If completed (True or "completed")
                    save_db_payload(
                        campaign_id,
                        {
                            "user_id": user_id,
                            "item_i": f"welcome_{i}",
                            "annotation": RESET_MARKER,
                        },
                    )
            # Reset progress to False for all welcome items
            num_welcome = len(progress_data[campaign_id][user_id]["progress_welcome"])
            progress_data[campaign_id][user_id]["progress_welcome"] = [
                False
            ] * num_welcome

        # Reset only the specified user's time
        _reset_user_time(progress_data, campaign_id, user_id)
        return JSONResponse(content="ok", status_code=200)
    elif assignment == "dynamic":
        # Reset only this user's completed items
        for item_i, item_progress in enumerate(
            progress_data[campaign_id][user_id]["progress"]
        ):
            if any(v == "completed" for v in item_progress.values()):
                save_db_payload(
                    campaign_id,
                    {"user_id": user_id, "item_i": item_i, "annotation": RESET_MARKER},
                )
                for model in item_progress:
                    if item_progress[model] == "completed":
                        item_progress[model] = None
        # Reset welcome items progress if it exists
        if "progress_welcome" in progress_data[campaign_id][user_id]:
            for i, status in enumerate(
                progress_data[campaign_id][user_id]["progress_welcome"]
            ):
                if status:
                    save_db_payload(
                        campaign_id,
                        {
                            "user_id": user_id,
                            "item_i": f"welcome_{i}",
                            "annotation": RESET_MARKER,
                        },
                    )
            num_welcome = len(progress_data[campaign_id][user_id]["progress_welcome"])
            progress_data[campaign_id][user_id]["progress_welcome"] = [
                False
            ] * num_welcome
        _reset_user_time(progress_data, campaign_id, user_id)
        return JSONResponse(content="ok", status_code=200)

    return JSONResponse(content="Unknown assignment type", status_code=400)


def update_progress(
    campaign_id: str,
    user_id: str,
    tasks_data: dict,
    progress_data: dict,
    item_i: int | str,  # Can be int or str like "welcome_0"
    payload: Any,
) -> JSONResponse:
    """
    Log the user's response for the specified item in the campaign.
    """
    # Check if it's a welcome item
    if isinstance(item_i, str) and item_i.startswith("welcome_"):
        welcome_index = int(item_i.split("_")[1])
        # Update only this user's progress_welcome (not shared)
        progress_data[campaign_id][user_id]["progress_welcome"][welcome_index] = (
            "completed"
        )
        return JSONResponse(content={"status": "ok"}, status_code=200)

    # Check if it's an item from data_random
    if isinstance(item_i, str) and item_i.startswith("random_"):
        # We don't store random item completion in progress_data,
        # it is purely for DB logging.
        return JSONResponse(content={"status": "ok"}, status_code=200)

    assignment = tasks_data[campaign_id]["info"]["assignment"]
    if assignment == "task-based":
        # Mark as completed for this user
        progress_data[campaign_id][user_id]["progress"][item_i] = "completed"
        return JSONResponse(content={"status": "ok"}, status_code=200)
    elif assignment == "single-stream":
        # Mark as completed for the current user, completed_foreign for others
        for uid in progress_data[campaign_id]:
            current_status = progress_data[campaign_id][uid]["progress"][item_i]
            if uid == user_id:
                # User who completed it gets "completed"
                progress_data[campaign_id][uid]["progress"][item_i] = "completed"
            elif current_status is None:
                # Other users get "completed_foreign" if not already completed
                progress_data[campaign_id][uid]["progress"][item_i] = (
                    "completed_foreign"
                )
            # If already "completed", keep it as "completed"
        return JSONResponse(content="ok", status_code=200)
    if assignment == "dynamic":
        # Mark as completed for the current user, completed_foreign for others
        for model in payload["annotation"][0].keys():
            for uid in progress_data[campaign_id]:
                current_status = progress_data[campaign_id][uid]["progress"][item_i][
                    model
                ]
                if uid == user_id:
                    # User who completed it gets "completed"
                    progress_data[campaign_id][uid]["progress"][item_i][model] = (
                        "completed"
                    )
                elif current_status is None:
                    # Other users get "completed_foreign" if not already completed
                    progress_data[campaign_id][uid]["progress"][item_i][model] = (
                        "completed_foreign"
                    )
                # If already "completed", keep it as "completed"
        return JSONResponse(content="ok", status_code=200)
    else:
        return JSONResponse(content="Unknown campaign assignment type", status_code=400)

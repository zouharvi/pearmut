import hashlib
import json
import os
import random

ROOT = os.environ.get("PEARMUT_ROOT", ".")
TOKEN_MAIN = os.environ.get("PEARMUT_TOKEN_MAIN", hashlib.sha256(random.randbytes(16)).hexdigest()[:10])

# Sentinel value to indicate a task reset - masks all prior annotations
RESET_MARKER = "__RESET__"


def load_progress_data(warn: str | None = None):
    data = {}
    progress_dir = f"{ROOT}/data/progress"
        
    for filename in os.listdir(progress_dir):
        if filename.endswith(".json"):
            campaign_id = filename.removesuffix(".json")
            with open(os.path.join(progress_dir, filename), "r") as f:
                data[campaign_id] = json.load(f)

    if not data and warn is not None:
        print(warn)
    return data


def save_progress_data(campaign_id: str, campaign_progress: dict):
    progress_dir = f"{ROOT}/data/progress"
    os.makedirs(progress_dir, exist_ok=True)
    with open(f"{progress_dir}/{campaign_id}.json", "w") as f:
        json.dump(campaign_progress, f, ensure_ascii=False)


_logs = {}


def get_db_log(campaign_id: str) -> list[dict]:
    """
    Returns up to date log for the given campaign_id.
    """
    if campaign_id not in _logs:
        # create a new one if it doesn't exist
        log_path = f"{ROOT}/data/annotations/{campaign_id}.jsonl"
        if os.path.exists(log_path):
            with open(log_path, "r") as f:
                _logs[campaign_id] = [json.loads(line) for line in f]
        else:
            _logs[campaign_id] = []

    return _logs[campaign_id]


def get_db_log_item(
    campaign_id: str, user_id: str | None, item_i: int | str | None
) -> list[dict]:
    """
    Returns the log item for the given campaign_id, user_id and item_i.
    Can be empty. Respects reset markers - if a reset marker is found,
    only entries after the last reset are returned.
    """
    log = get_db_log(campaign_id)

    # Filter matching entries
    matching = [
        entry
        for entry in log
        if (
            (user_id is None or entry.get("user_id") == user_id)
            and (item_i is None or entry.get("item_i") == item_i)
        )
    ]

    # Find the last reset marker for this user (if any)
    last_reset_idx = -1
    for i, entry in enumerate(matching):
        if entry.get("annotation") == RESET_MARKER:
            last_reset_idx = i

    # Return only entries after the last reset
    if last_reset_idx >= 0:
        matching = matching[last_reset_idx + 1 :]

    return matching


def save_db_payload(campaign_id: str, payload: dict):
    """
    Saves the given payload to the log for the given campaign_id, user_id and item_i.
    Saves both on disk and in-memory.
    """
    # Ensure the in-memory cache is initialized before writing to file
    # to avoid reading back the same entry we're about to append
    log = get_db_log(campaign_id)

    log_path = f"{ROOT}/data/annotations/{campaign_id}.jsonl"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a") as log_file:
        log_file.write(
            json.dumps(
                payload,
                ensure_ascii=False,
            )
            + "\n"
        )

    log.append(payload)


def check_validation_threshold(
    campaigns_data: dict,
    progress_data: dict,
    campaign_id: str,
    user_id: str,
) -> bool:
    """
    Check if user passes the validation threshold.

    The threshold is defined in campaign info as 'validation_threshold':
    - If integer: pass if number of failed checks <= threshold
    - If float in [0, 1): pass if proportion of failed checks <= threshold
    - If float >= 1: always fail
    - If None/not set: defaults to 0 (fail on any failed check)

    Returns True if validation passes, False otherwise.
    """
    threshold = campaigns_data[campaign_id]["info"].get("validation_threshold", 0)

    user_progress = progress_data[campaign_id][user_id]
    validations = user_progress.get("validations", {})

    # Count failed checks (validations is dict of item_i -> list of bools)
    total_checks = 0
    failed_checks = 0
    for item_validations in validations.values():
        for check_passed in item_validations:
            total_checks += 1
            if not check_passed:
                failed_checks += 1

    # If no validation checks exist, pass
    if total_checks == 0:
        return True

    # Float >= 1: always fail
    if isinstance(threshold, float) and threshold >= 1:
        return False

    # Check threshold based on type
    if isinstance(threshold, float):
        # Float in [0, 1): proportion-based, pass if failed proportion <= threshold
        return failed_checks / total_checks <= threshold
    else:
        # Integer: count-based, pass if failed count <= threshold
        return failed_checks <= threshold


def is_form_document(items):
    """Check if a document contains form items instead of evaluation items."""
    if not items:
        return False
    # Check if first item has 'text' and 'form' keys (form item)
    first_item = items[0]
    return "text" in first_item and "form" in first_item


def shuffled(lst):
    """Return a shuffled copy of the input list."""
    lst_copy = list(lst)
    random.shuffle(lst_copy)
    return lst_copy
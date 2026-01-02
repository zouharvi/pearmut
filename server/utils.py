import json
import os

ROOT = "."

# Sentinel value to indicate a task reset - masks all prior annotations
RESET_MARKER = "__RESET__"


def load_progress_data(warn: str | None = None):
    if not os.path.exists(f"{ROOT}/data/progress.json"):
        if warn is not None:
            print(warn)
        with open(f"{ROOT}/data/progress.json", "w") as f:
            f.write(json.dumps({}))
    with open(f"{ROOT}/data/progress.json", "r") as f:
        data = json.load(f)
    
    return data


def save_progress_data(data):
    with open(f"{ROOT}/data/progress.json", "w") as f:
        json.dump(data, f, indent=2)


_logs = {}


def get_db_log(campaign_id: str) -> list[dict]:
    """
    Returns up to date log for the given campaign_id.
    """
    if campaign_id not in _logs:
        # create a new one if it doesn't exist
        log_path = f"{ROOT}/data/outputs/{campaign_id}.jsonl"
        if os.path.exists(log_path):
            with open(log_path, "r") as f:
                _logs[campaign_id] = [
                    json.loads(line) for line in f.readlines()
                ]
        else:
            _logs[campaign_id] = []

    return _logs[campaign_id]


def get_db_log_item(campaign_id: str, user_id: str | None, item_i: int | None) -> list[dict]:
    """
    Returns the log item for the given campaign_id, user_id and item_i.
    Can be empty. Respects reset markers - if a reset marker is found,
    only entries after the last reset are returned.
    """
    log = get_db_log(campaign_id)
    
    # Filter matching entries
    matching = [
        entry for entry in log
        if (
            (user_id is None or entry.get("user_id") == user_id) and
            (item_i is None or entry.get("item_i") == item_i)
        )
    ]
    
    # Find the last reset marker for this user (if any)
    last_reset_idx = -1
    for i, entry in enumerate(matching):
        if entry.get("annotation") == RESET_MARKER:
            last_reset_idx = i
    
    # Return only entries after the last reset
    if last_reset_idx >= 0:
        matching = matching[last_reset_idx + 1:]
    
    return matching


def save_db_payload(campaign_id: str, payload: dict):
    """
    Saves the given payload to the log for the given campaign_id, user_id and item_i.
    Saves both on disk and in-memory.
    """
    # Ensure the in-memory cache is initialized before writing to file
    # to avoid reading back the same entry we're about to append
    log = get_db_log(campaign_id)

    log_path = f"{ROOT}/data/outputs/{campaign_id}.jsonl"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a") as log_file:
        log_file.write(json.dumps(payload, ensure_ascii=False,) + "\n")

    log.append(payload)


def check_validation_threshold(
    tasks_data: dict,
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
    threshold = tasks_data[campaign_id]["info"].get("validation_threshold", 0)
    
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

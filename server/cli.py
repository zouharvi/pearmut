"""
Command-line interface for managing and running the Pearmut server.
"""

import argparse
import atexit
import hashlib
import json
import os
import shutil
import urllib.parse

from .utils import (
    ROOT,
    TOKEN_MAIN,
    is_form_document,
    load_progress_data,
    save_progress_data,
)

os.makedirs(f"{ROOT}/data/campaigns", exist_ok=True)
os.makedirs(f"{ROOT}/data/outputs", exist_ok=True)
os.makedirs(f"{ROOT}/data/annotations", exist_ok=True)
os.makedirs(f"{ROOT}/data/progress", exist_ok=True)

# NOTE: migration scripts will be removed in the next minor release, i.e. 1.2.0

# migration to move data/tasks to data/campaigns if it exists
if os.path.exists(f"{ROOT}/data/tasks"):
    for item in os.listdir(f"{ROOT}/data/tasks"):
        src = os.path.join(f"{ROOT}/data/tasks", item)
        dst = os.path.join(f"{ROOT}/data/campaigns", item)
        if not os.path.exists(dst):
            shutil.move(src, dst)
    # if empty
    if not os.listdir(f"{ROOT}/data/tasks"):
        shutil.rmtree(f"{ROOT}/data/tasks")
    else:
        print(f"Warning: {ROOT}/data/tasks is not empty after migration. Please investigate.")

# migration to move data/outputs to data/annotations if it exists
if os.path.exists(f"{ROOT}/data/outputs"):
    for item in os.listdir(f"{ROOT}/data/outputs"):
        src = os.path.join(f"{ROOT}/data/outputs", item)
        dst = os.path.join(f"{ROOT}/data/annotations", item)
        if not os.path.exists(dst):
            shutil.move(src, dst)
    # if empty
    if not os.listdir(f"{ROOT}/data/outputs"):
        shutil.rmtree(f"{ROOT}/data/outputs")
    else:
        print(f"Warning: {ROOT}/data/outputs is not empty after migration. Please investigate.")

# migration to split progress.json into per-campaign files
if os.path.exists(f"{ROOT}/data/progress.json"):
    print("Migrating progress.json to per-campaign files...")
    os.makedirs(f"{ROOT}/data/progress", exist_ok=True)
    with open(f"{ROOT}/data/progress.json", "r") as f:
        try:
            old_progress = json.load(f)
        except json.JSONDecodeError:
            old_progress = {}
    for c_id, data in old_progress.items():
        with open(f"{ROOT}/data/progress/{c_id}.json", "w") as f:
            json.dump(data, f, ensure_ascii=False)
    os.remove(f"{ROOT}/data/progress.json")


load_progress_data(warn=None)


def _run(args_unknown):
    import uvicorn
    import uvicorn.config

    from .app import app, tasks_data

    args = argparse.ArgumentParser()
    args.add_argument(
        "--port", type=int, default=8001, help="Port to run the server on"
    )
    args.add_argument(
        "--url",
        default="localhost",
        help="Prefix server URL for protocol links",
    )
    args = args.parse_args(args_unknown)

    if args.url in {"localhost", "127.0.0.1", "0.0.0.0"}:
        args.url = f"http://{args.url}:{args.port}"

    # print access dashboard URL for all campaigns
    dashboard_url = (
        args.url
        + f"/dashboard?token_main={TOKEN_MAIN}"
        + "".join(
            [
                f"&campaign_id={urllib.parse.quote_plus(campaign_id)}&token={campaign_data['token']}"
                for campaign_id, campaign_data in tasks_data.items()
            ]
        )
    )
    print(
        "\033[92mNow serving Pearmut, use the following URL to access the everything-dashboard:\033[0m"
    )
    print("🍐", dashboard_url + "\n", flush=True)

    # disable startup message
    uvicorn.config.LOGGING_CONFIG["loggers"]["uvicorn.error"]["level"] = "WARNING"
    # set time logging
    uvicorn.config.LOGGING_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M"
    uvicorn.config.LOGGING_CONFIG["formatters"]["access"]["fmt"] = (
        "%(asctime)s %(levelprefix)s %(client_addr)s - %(request_line)s %(status_code)s"
    )
    uvicorn.run(
        app,
        # bind to all interfaces
        host="0.0.0.0",
        port=args.port,
        reload=False,
    )


def _validate_item_structure(items):
    """
    Validate that items have the correct structure.
    Items can be either:
    1. Evaluation items: dictionaries with 'tgt' and optionally 'src' and/or 'ref' keys
    2. Form items: dictionaries with 'text' and 'form' keys

    A document must contain either all evaluation items or all form items (not mixed).

    Args:
        items: List of item dictionaries to validate
    """
    if not isinstance(items, list):
        raise ValueError("Items must be a list")

    if not items:
        raise ValueError("Items list cannot be empty")

    # Check if first item is a form item or evaluation item
    first_item = items[0]
    if not isinstance(first_item, dict):
        raise ValueError("Each item must be a dictionary")

    first_item_is_form = "text" in first_item and "form" in first_item

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each item must be a dictionary")

        # Check consistency: all items must be same type (form or evaluation)
        current_is_form = "text" in item and "form" in item
        if current_is_form != first_item_is_form:
            raise ValueError("Document cannot mix form items and evaluation items")

        if first_item_is_form:
            # Validate form item structure
            if "text" not in item:
                raise ValueError("Form item must contain 'text' key")
            if "form" not in item:
                raise ValueError("Form item must contain 'form' key")
            if not isinstance(item["text"], str):
                raise ValueError("Form item 'text' must be a string")
            if item["form"] not in {None, "number", "string", "choices", "script"}:
                raise ValueError(
                    "Form item 'form' must be null, 'number', 'string', 'choices', or 'script'"
                )
        else:
            # Validate evaluation item structure
            if "tgt" not in item:
                raise ValueError("Each item must contain 'tgt' key")

            # Validate src is a string if present
            if "src" in item and not isinstance(item["src"], str):
                raise ValueError("Item 'src' must be a string")

            # Validate ref is a string if present
            if "ref" in item and not isinstance(item["ref"], str):
                raise ValueError("Item 'ref' must be a string")

            # Validate tgt is a dictionary (annotate template with model names)
            if isinstance(item["tgt"], str):
                # String not allowed - suggest using dictionary (don't include user input to prevent injection)
                raise ValueError(
                    'Item \'tgt\' must be a dictionary mapping model names to translations. For single translation, use {"default": "your_translation"}'
                )
            elif isinstance(item["tgt"], dict):
                # Dictionary mapping model names to translations
                # Validate that model names don't contain only numbers (JavaScript ordering issue)
                for model_name, translation in item["tgt"].items():
                    if not isinstance(model_name, str):
                        raise ValueError(
                            "Model names in 'tgt' dictionary must be strings"
                        )
                    if model_name.isdigit():
                        raise ValueError(
                            f"Model name '{model_name}' cannot be only numeric digits (would cause issues in JS/TS)"
                        )
                    if not isinstance(translation, str):
                        raise ValueError(
                            f"Translation for model '{model_name}' must be a string"
                        )
            else:
                raise ValueError(
                    "Item 'tgt' must be a dictionary mapping model names to translations"
                )

            # Validate error_spans structure if present
            if "error_spans" in item:
                if not isinstance(item["error_spans"], dict):
                    raise ValueError(
                        "'error_spans' must be a dictionary mapping model names to error span lists"
                    )
                for model_name, spans in item["error_spans"].items():
                    if not isinstance(spans, list):
                        raise ValueError(
                            f"Error spans for model '{model_name}' must be a list"
                        )

            # Validate validation structure if present
            if "validation" in item:
                if not isinstance(item["validation"], dict):
                    raise ValueError(
                        "'validation' must be a dictionary mapping model names to validation rules"
                    )
                for model_name, val_rule in item["validation"].items():
                    if not isinstance(val_rule, dict):
                        raise ValueError(
                            f"Validation rule for model '{model_name}' must be a dictionary"
                        )


def _validate_document_models(doc):
    """
    Validate that all items in a document have the same model outputs.

    Args:
        doc: List of items in a document

    Returns:
        None if valid

    Raises:
        ValueError: If items have different model outputs
    """
    # Get model names from the first item
    first_item = doc[0]
    first_models = set(first_item["tgt"].keys())

    # Check all other items have the same model names
    for i, item in enumerate(doc[1:], start=1):
        if "tgt" not in item or not isinstance(item["tgt"], dict):
            continue

        item_models = set(item["tgt"].keys())
        if item_models != first_models:
            raise ValueError(
                f"Document contains items with different model outputs. "
                f"Item 0 has models {sorted(first_models)}, but item {i} has models {sorted(item_models)}. "
                f"This is fine, but we can't shuffle (on by default). "
                f"To fix this, set 'shuffle': false in the campaign 'info' section. "
            )


def _shuffle_campaign_data(campaign_data, rng):
    """
    Shuffle campaign data at the document level in-place

    For each document, randomly shuffles the order of models in the tgt dictionary.

    Args:
        campaign_data: The campaign data dictionary
        rng: Random number generator with campaign-specific seed
    """

    def shuffle_document(doc):
        """Shuffle a single document (list of items) by reordering models in tgt dict."""
        # Skip shuffling for form documents (they don't have tgt)
        if is_form_document(doc):
            return  # Form documents don't need shuffling

        # Validate that all items have the same models
        _validate_document_models(doc)

        # Get all model names from the first item's tgt dict
        first_item = doc[0]
        model_names = list(first_item["tgt"].keys())
        rng.shuffle(model_names)

        # Reorder tgt dict for all items in the document
        for item in doc:
            if "tgt" in item and isinstance(item["tgt"], dict):
                item["tgt"] = {model: item["tgt"][model] for model in model_names}

    assignment = campaign_data["info"]["assignment"]

    if assignment == "task-based":
        # After transformation, data is a dict mapping user_id -> tasks
        for user_id, task in campaign_data["data"].items():
            for doc in task:
                shuffle_document(doc)
    elif assignment in ["single-stream", "dynamic"]:
        # Shuffle each document in the shared pool
        for doc in campaign_data["data"]:
            shuffle_document(doc)


def _add_single_campaign(campaign_data, overwrite, url):
    """
    Add a single campaign from campaign data dictionary.
    """
    import random

    import wonderwords

    if "campaign_id" not in campaign_data:
        raise ValueError("Campaign data must contain 'campaign_id' field.")
    if "data" not in campaign_data:
        raise ValueError("Campaign data must contain 'data' field.")
    
    # this should be fine, can rely on defaults
    campaign_data["info"] = campaign_data.get("info", {})

    progress_data = load_progress_data()

    if campaign_data["campaign_id"] in progress_data and not overwrite:
        raise ValueError(
            f"Campaign {campaign_data['campaign_id']} already exists.\n"
            "Use -o to overwrite."
        )

    if "assignment" not in campaign_data["info"]:
        campaign_data["info"]["assignment"] = "single-stream"
        print("Warning: 'assignment' not specified in campaign info. Defaulting to 'single-stream'.")

    if "users" not in campaign_data["info"]:
        campaign_data["info"]["users"] = 1
        print("Warning: 'users' not specified in campaign info. Defaulting to 1 user.")

    # Template defaults to "annotate" if not specified
    assignment = campaign_data["info"]["assignment"]
    # use random words for identifying users
    rng = random.Random()
    rword = wonderwords.RandomWord(rng=rng)

    # Parse users specification from info
    users_spec = campaign_data["info"]["users"]
    user_tokens = {}  # user_id -> {"pass": ..., "fail": ...}

    # Validate and process data_welcome if present
    data_welcome = campaign_data.get("data_welcome", [])
    if data_welcome:
        if not isinstance(data_welcome, list):
            raise ValueError("'data_welcome' must be a list of documents.")
        # Validate welcome documents structure - each should be a list of items
        for doc_i, doc in enumerate(data_welcome):
            if not isinstance(doc, list):
                raise ValueError(f"Welcome document {doc_i} must be a list of items.")
            try:
                _validate_item_structure(doc)
            except ValueError as e:
                raise ValueError(f"Welcome document {doc_i}: {e}")

    # Validate and process data_random if present
    data_random = campaign_data.get("data_random", [])
    if data_random:
        if not isinstance(data_random, list):
            raise ValueError("'data_random' must be a list of documents.")
        # Validate random documents structure - each should be a list of items
        for doc_i, doc in enumerate(data_random):
            if not isinstance(doc, list):
                raise ValueError(f"Random document {doc_i} must be a list of items.")
            try:
                _validate_item_structure(doc)
            except ValueError as e:
                raise ValueError(f"Random document {doc_i}: {e}")
        if "data_random_prob" not in campaign_data["info"]:
            raise ValueError("'data_random_prob' must be in 'info' when 'data_random' is present.")
        data_random_prob = campaign_data["info"]["data_random_prob"]
        if not isinstance(data_random_prob, float) or not (0 <= data_random_prob <= 1):
            raise ValueError("'data_random_prob' must be a float between 0 and 1 (probability)")

    if assignment == "task-based":
        tasks = campaign_data["data"]
        if isinstance(tasks, dict) and all(isinstance(v, list) for v in tasks.values()):
            # Already a dict mapping user_id -> tasks (probably from a running campaign), extract just the tasks
            tasks = list(tasks.values())
        if not isinstance(tasks, list):
            raise ValueError("Task-based campaign 'data' must be a list of tasks.")
        if not all(isinstance(task, list) for task in tasks):
            raise ValueError(
                "Each task in task-based campaign 'data' must be a list of items."
            )
        # Validate item structure for each task
        for task_i, task in enumerate(tasks):
            for doc_i, doc in enumerate(task):
                try:
                    _validate_item_structure(doc)
                except ValueError as e:
                    raise ValueError(f"Task {task_i}, document {doc_i}: {e}")
        num_users = len(tasks)
    elif assignment == "single-stream":
        tasks = campaign_data["data"]
        if not isinstance(campaign_data["data"], list):
            raise ValueError("Single-stream campaign 'data' must be a list of items.")
        # Validate item structure for single-stream
        for doc_i, doc in enumerate(tasks):
            try:
                _validate_item_structure(doc)
            except ValueError as e:
                raise ValueError(f"Document {doc_i}: {e}")
        if isinstance(users_spec, int):
            num_users = users_spec
        elif isinstance(users_spec, list):
            num_users = len(users_spec)
        else:
            raise ValueError("'users' must be an integer or a list.")
    elif assignment == "dynamic":
        tasks = campaign_data["data"]
        if not isinstance(campaign_data["data"], list):
            raise ValueError("Dynamic campaign 'data' must be a list of items.")
        # Validate item structure for dynamic
        for doc_i, doc in enumerate(tasks):
            try:
                _validate_item_structure(doc)
            except ValueError as e:
                raise ValueError(f"Document {doc_i}: {e}")
        if isinstance(users_spec, int):
            num_users = users_spec
        elif isinstance(users_spec, list):
            num_users = len(users_spec)
        else:
            raise ValueError("'users' must be an integer or a list.")
        # Validate dynamic-specific parameters
        if "dynamic_warmup" not in campaign_data["info"]:
            campaign_data["info"]["dynamic_warmup"] = 5
        if "dynamic_models" not in campaign_data["info"]:
            campaign_data["info"]["dynamic_models"] = 1
        # Validate that dynamic_warmup is at least 1
        assert campaign_data["info"]["dynamic_warmup"] >= 1, (
            "dynamic_warmup must be at least 1"
        )
        # Validate that all items have the same models
        all_models = set()
        for item in campaign_data["data"]:
            if item and len(item) > 0:
                all_models.update(item[0]["tgt"].keys())
        for item in campaign_data["data"]:
            if item and len(item) > 0:
                item_models = set(item[0]["tgt"].keys())
                assert item_models == all_models, (
                    "All items must have the same model outputs"
                )
    else:
        raise ValueError(f"Unknown campaign assignment type: {assignment}")

    # Generate or parse user IDs based on users specification
    if users_spec is None or isinstance(users_spec, int):
        # Generate random user IDs
        user_ids = []
        while len(user_ids) < num_users:
            new_id = f"{rword.random_words(amount=1, include_parts_of_speech=['adjective'])[0]}-{rword.random_words(amount=1, include_parts_of_speech=['noun'])[0]}"
            if new_id not in user_ids:
                user_ids.append(new_id)
        user_ids = [f"{user_id}-{rng.randint(0, 999):03d}" for user_id in user_ids]
    elif isinstance(users_spec, list):
        if len(users_spec) != num_users:
            raise ValueError(
                f"Number of users ({len(users_spec)}) must match expected count ({num_users})."
            )
        if all(isinstance(u, str) for u in users_spec):
            # List of string IDs
            user_ids = users_spec
        elif all(isinstance(u, dict) for u in users_spec):
            # List of dicts with user_id, token_pass, token_fail
            user_ids = []
            for u in users_spec:
                if "user_id" not in u:
                    raise ValueError("Each user dict must contain 'user_id'.")
                user_ids.append(u["user_id"])
                user_tokens[u["user_id"]] = {
                    "pass": u.get("token_pass"),
                    "fail": u.get("token_fail"),
                }
        else:
            raise ValueError("'users' list must contain all strings or all dicts.")
    else:
        raise ValueError("'users' must be an integer or a list.")

    if "protocol" not in campaign_data["info"]:
        campaign_data["info"]["protocol"] = "cESA"
        print("Warning: 'protocol' not specified in campaign info. Defaulting to 'cESA'.")

    protocol = campaign_data["info"]["protocol"]
    if "special_tokens" not in campaign_data["info"]:
        if protocol in {"ESA", "cESA", "MQM"}:
            campaign_data["info"]["special_tokens"] = ["[missing]"]
        else:
            campaign_data["info"]["special_tokens"] = []

    # Validate sliders structure if present
    if "sliders" in campaign_data["info"]:
        if not all(
            isinstance(s, dict)
            and all(k in s for k in ("name", "min", "max", "step"))
            and isinstance(s.get("min"), (int, float))
            and isinstance(s.get("max"), (int, float))
            and isinstance(s.get("step"), (int, float))
            and s["min"] <= s["max"]
            and s["step"] > 0
            for s in campaign_data["info"]["sliders"]
        ):
            raise ValueError(
                "Each slider must be a dict with 'name', 'min', 'max', and 'step' keys, where min/max/step are numeric, min <= max, and step > 0"
            )

    # Remove output file when overwriting (after all validations pass)
    if overwrite and campaign_data["campaign_id"] in progress_data:
        output_file = f"{ROOT}/data/annotations/{campaign_data['campaign_id']}.jsonl"
        if os.path.exists(output_file):
            os.remove(output_file)

    # For task-based, data is a dict mapping user_id -> tasks
    # For single-stream and dynamic, data is a flat list (shared among all users)
    if assignment == "task-based":
        campaign_data["data"] = {
            user_id: task for user_id, task in zip(user_ids, tasks)
        }
    elif assignment in {"single-stream", "dynamic"}:
        campaign_data["data"] = tasks

    # generate a token for dashboard access if not present
    if "token" not in campaign_data:
        campaign_data["token"] = hashlib.sha256(random.randbytes(16)).hexdigest()[:10]

    def get_token(user_id, token_type):
        """Get user token or generate a random one."""
        token = user_tokens.get(user_id, {}).get(token_type)
        if token is not None:
            return token
        return hashlib.sha256(random.randbytes(16)).hexdigest()[:10]

    user_progress = {
        user_id: {
            # Progress tracking: None | "completed" for task-based,
            # None | "completed" | "completed_foreign" for single-stream/dynamic
            "progress": (
                [None] * len(campaign_data["data"][user_id])
                if assignment == "task-based"
                else [None] * len(campaign_data["data"])
                if assignment == "single-stream"
                else [{model: None for model in all_models}] # pyright: ignore[reportPossiblyUnboundVariable]
                * len(campaign_data["data"])
                if assignment == "dynamic"
                else int(f"Invalid assignment: {assignment}")
            ),
            "progress_welcome": [None] * len(data_welcome),
            "time_start": None,
            "time_end": None,
            "time": 0,
            "url": (
                f"{campaign_data['info'].get('template', 'annotate')}"
                f"?campaign_id={urllib.parse.quote_plus(campaign_data['campaign_id'])}"
                f"&user_id={user_id}"
            ),
            "token_correct": get_token(user_id, "pass"),
            "token_incorrect": get_token(user_id, "fail"),
        }
        for user_id in user_ids
    }

    # Handle assets symlink if specified
    if "assets" in campaign_data["info"]:
        assets_config = campaign_data["info"]["assets"]

        # assets must be a dictionary with source and destination keys
        if not isinstance(assets_config, dict):
            raise ValueError(
                "Assets must be a dictionary with 'source' and 'destination' keys."
            )
        if "source" not in assets_config or "destination" not in assets_config:
            raise ValueError(
                "Assets config must contain 'source' and 'destination' keys."
            )

        assets_source = assets_config["source"]
        assets_destination = assets_config["destination"]

        # Validate destination starts with 'assets/'
        if not assets_destination.startswith("assets/"):
            raise ValueError(
                f"Assets destination '{assets_destination}' must start with 'assets/'."
            )

        # Resolve relative paths from the caller's current working directory
        assets_real_path = os.path.abspath(assets_source)

        if not os.path.isdir(assets_real_path):
            raise ValueError(
                f"Assets source path '{assets_real_path}' must be an existing directory."
            )

        # Symlink path is based on the destination, stripping the 'assets/' prefix
        # User assets are now stored under data/assets/ instead of static/assets/
        symlink_path = f"{ROOT}/data/{assets_destination}".rstrip("/")

        # Remove existing symlink if present and we are overriding the same campaign
        if os.path.lexists(symlink_path):
            # Check if any other campaign is using this destination
            current_campaign_id = campaign_data["campaign_id"]

            for other_campaign_id in progress_data.keys():
                if other_campaign_id == current_campaign_id:
                    continue
                with open(f"{ROOT}/data/campaigns/{other_campaign_id}.json", "r") as f:
                    other_campaign = json.load(f)
                    other_assets = other_campaign.get("info", {}).get("assets")
                    if other_assets:
                        if other_assets.get("destination") == assets_destination:
                            raise ValueError(
                                f"Assets destination '{assets_destination}' is already used by campaign '{other_campaign_id}'."
                            )
            # Only allow overwrite if it's the same campaign
            if overwrite:
                os.remove(symlink_path)
            else:
                raise ValueError(
                    f"Assets destination '{assets_destination}' is already taken."
                )

        # Ensure the assets directory exists
        # get parent of symlink_path dir
        os.makedirs(os.path.dirname(symlink_path), exist_ok=True)

        os.symlink(assets_real_path, symlink_path, target_is_directory=True)
        print(f"Assets symlinked: {symlink_path} -> {assets_real_path}")

    # Shuffle data if shuffle parameter is true (defaults to true)
    should_shuffle = campaign_data["info"].get("shuffle", True)
    if should_shuffle:
        _shuffle_campaign_data(campaign_data, rng)

    # commit to transaction
    with open(f"{ROOT}/data/campaigns/{campaign_data['campaign_id']}.json", "w") as f:
        json.dump(campaign_data, f, indent=2, ensure_ascii=False)

    progress_data[campaign_data["campaign_id"]] = user_progress
    save_progress_data(campaign_data["campaign_id"], progress_data[campaign_data["campaign_id"]])

    if url is not None:
        print(
            "🎛️ ",
            f"{url}/dashboard.html"
            f"?campaign_id={urllib.parse.quote_plus(campaign_data['campaign_id'])}"
            f"&token={campaign_data['token']}",
        )
        for user_id, user_val in user_progress.items():
            # point to the protocol URL
            print(f"🧑 {url}/{user_val['url']}")
        print()


def _add_campaign(args_unknown):
    """
    Add campaigns from one or more JSON data files.
    """
    args = argparse.ArgumentParser(
        prog="pearmut add",
        description="Add campaigns from one or more JSON data files."
    )
        
    args.add_argument(
        "data_files",
        type=str,
        nargs="+",
        help="One or more paths to campaign data files",
    )
    args.add_argument(
        "-o",
        "--overwrite",
        action="store_true",
        help="Overwrite existing campaign if it exists",
    )
    args.add_argument(
        "--url",
        default="http://localhost:8001",
        help="Prefix server URL for protocol links",
    )
    args = args.parse_args(args_unknown)

    for data_file in args.data_files:
        try:
            with open(data_file, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for campaign in data:
                        _add_single_campaign(campaign, args.overwrite, args.url)
                else:
                    _add_single_campaign(data, args.overwrite, args.url)
        except Exception as e:
            print(f"Error processing {data_file}: {e}")
            exit(1)


def _add_existing(args_unknown):
    """
    Add existing campaigns from JSON data files, importing their progress and annotations.
    """
    args = argparse.ArgumentParser(
        prog="pearmut add-existing",
        description="Import campaigns with existing progress and annotations from external files."
    )
    if not args_unknown:
        args.print_help()
        import sys
        sys.exit(1)
        
    args.add_argument(
        "data_files",
        type=str,
        nargs="+",
        help="One or more paths to campaign data files",
    )
    args.add_argument(
        "--progress",
        type=str,
        required=True,
        help="Path to the progress.json file to import",
    )
    args.add_argument(
        "--annotations",
        type=str,
        required=True,
        help="Path to the file containing annotation JSONL",
    )
    args.add_argument(
        "-o",
        "--overwrite",
        action="store_true",
        help="Overwrite existing campaign if it exists",
    )
    args.add_argument(
        "--url",
        default="http://localhost:8001",
        help="Prefix server URL for protocol links",
    )
    args = args.parse_args(args_unknown)

    local_progress = load_progress_data()

    with open(args.progress, "r") as f:
        ext_progress = json.load(f)

    with open(args.annotations, "r") as f:
        ext_annotations = json.load(f)

    for data_file in args.data_files:
        try:
            with open(data_file, "r") as f:
                data = json.load(f)
            
            campaigns = data if isinstance(data, list) else [data]
            
            for campaign in campaigns:
                campaign_id = campaign.get("campaign_id")
                if not campaign_id:
                    print(f"Skipping a campaign without campaign_id in {data_file}")
                    continue
                
                if campaign_id in local_progress and not args.overwrite:
                    raise ValueError(f"Campaign {campaign_id} already exists locally. Use -o to overwrite.")
                
                if campaign_id not in ext_progress:
                    raise ValueError(f"Campaign {campaign_id} not found in the provided progress.json.")
                
                if campaign_id not in ext_annotations:
                    raise ValueError(f"Campaign {campaign_id} not found in the provided annotations file.")
                
                import hashlib
                import random
                if "token" not in campaign:
                    campaign["token"] = hashlib.sha256(random.randbytes(16)).hexdigest()[:10]
                
                local_progress[campaign_id] = ext_progress[campaign_id]
                save_progress_data(campaign_id, local_progress[campaign_id])
                
                with open(f"{ROOT}/data/campaigns/{campaign_id}.json", "w") as f:
                    json.dump(campaign, f, indent=2, ensure_ascii=False)
                
                os.makedirs(f"{ROOT}/data/outputs", exist_ok=True)
                with open(f"{ROOT}/data/annotations/{campaign_id}.jsonl", "w") as f_out:
                    for record in ext_annotations[campaign_id]:
                        f_out.write(json.dumps(record, ensure_ascii=False) + "\n")
                
                print(f"Successfully imported campaign {campaign_id}")
                print(
                    "🎛️ ",
                    f"{args.url}/dashboard.html"
                    f"?campaign_id={urllib.parse.quote_plus(campaign['campaign_id'])}"
                    f"&token={campaign['token']}",
                )
                for user_id, user_val in ext_progress[campaign_id].items():
                    print(f"🧑 {args.url}/{user_val['url']}")
                print()
                
        except Exception as e:
            print(f"Error processing {data_file}: {e}")
            exit(1)


def main():
    """
    Main entry point for the CLI.
    """

    # Acquire lock before starting server
    lock_file = f"{ROOT}/data/.lock"
    if os.path.exists(lock_file):
        with open(lock_file, "r") as f:
            pid = f.read().strip()
        print(
            f"Another instance (PID {pid}) is already running in the same directory. We know this because {lock_file} exists."
        )
        exit(1)

    with open(lock_file, "w") as f:
        f.write(str(os.getpid()))

    # Register cleanup to remove lock file on exit
    atexit.register(lambda: os.path.exists(lock_file) and os.remove(lock_file))

    args = argparse.ArgumentParser()
    args.add_argument(
        "command",
        type=str,
        choices=["run", "add", "purge", "add-existing", "bake-existing"],
        default="run",
        nargs="?",
    )
    args, args_unknown = args.parse_known_args()

    if args.command == "run":
        _run(args_unknown)
    elif args.command == "add":
        _add_campaign(args_unknown)
    elif args.command == "add-existing":
        _add_existing(args_unknown)
    elif args.command == "purge":
        import shutil

        def _unlink_assets(campaign_id):
            """Unlink assets symlink for a campaign if it exists."""
            task_file = f"{ROOT}/data/campaigns/{campaign_id}.json"
            if not os.path.exists(task_file):
                return
            with open(task_file, "r") as f:
                campaign_data = json.load(f)
            destination = (
                campaign_data.get("info", {}).get("assets", {}).get("destination")
            )
            if destination:
                symlink_path = f"{ROOT}/data/{destination}".rstrip("/")
                if os.path.islink(symlink_path):
                    os.remove(symlink_path)
                    print(f"Assets symlink removed: {symlink_path}")

        # Parse optional campaign name
        purge_args = argparse.ArgumentParser()
        purge_args.add_argument(
            "campaign",
            type=str,
            nargs="?",
            default=None,
            help="Optional campaign name to purge (purges all if not specified)",
        )
        purge_args = purge_args.parse_args(args_unknown)
        progress_data = load_progress_data()

        if purge_args.campaign is not None:
            # Purge specific campaign
            campaign_id = purge_args.campaign
            if campaign_id not in progress_data:
                print(f"Campaign '{campaign_id}' does not exist.")
                return
            confirm = input(
                f"Are you sure you want to purge campaign '{campaign_id}'? This action cannot be undone. [y/n] "
            )
            if confirm.lower() == "y":
                # Unlink assets before removing task file
                _unlink_assets(campaign_id)
                # Remove task file
                task_file = f"{ROOT}/data/campaigns/{campaign_id}.json"
                if os.path.exists(task_file):
                    os.remove(task_file)
                # Remove output file
                output_file = f"{ROOT}/data/annotations/{campaign_id}.jsonl"
                if os.path.exists(output_file):
                    os.remove(output_file)
                # Remove from progress data
                progress_data = load_progress_data()
                if campaign_id in progress_data:
                    del progress_data[campaign_id]
                    progress_file = f"{ROOT}/data/progress/{campaign_id}.json"
                    if os.path.exists(progress_file):
                        os.remove(progress_file)
                print(f"Campaign '{campaign_id}' purged.")
            else:
                print("Cancelled.")
        else:
            # Purge all campaigns
            confirm = input(
                "Are you sure you want to purge all campaign data? This action cannot be undone. [y/n] "
            )
            if confirm.lower() == "y":
                # Unlink all assets first
                for campaign_id in progress_data.keys():
                    _unlink_assets(campaign_id)
                shutil.rmtree(f"{ROOT}/data/campaigns", ignore_errors=True)
                shutil.rmtree(f"{ROOT}/data/outputs", ignore_errors=True)
                if os.path.exists(f"{ROOT}/data/progress"):
                    shutil.rmtree(f"{ROOT}/data/progress", ignore_errors=True)
                print("All campaign data purged.")
            else:
                print("Cancelled.")
    elif args.command == "bake-existing":
        _bake_existing(args_unknown)


def _bake_existing(args_unknown):
    import json
    import os
    import subprocess

    from .assignment import CAMPAIGN_INFO_PUBLIC, _get_instructions
    from .utils import is_form_document

    args = argparse.ArgumentParser(
        prog="pearmut bake-existing",
        description="Bake an existing campaign into static files."
    )
    args.add_argument(
        "data_files",
        type=str,
        nargs="+",
        help="One or more paths to campaign data files",
    )
    args.add_argument(
        "--progress",
        type=str,
        required=True,
        help="Path to the progress.json file to import",
    )
    args.add_argument(
        "--annotations",
        type=str,
        required=True,
        help="Path to the annotation JSONL file",
    )
    args.add_argument(
        "--output",
        "-o",
        type=str,
        default="baked_output",
        help="Output directory for the baked static files",
    )
    args = args.parse_args(args_unknown)
    
    with open(args.progress, "r") as f:
        ext_progress = json.load(f)

    with open(args.annotations, "r") as f:
        ext_annotations = json.load(f)

    tasks_data = {}
    for data_file in args.data_files:
        with open(data_file, "r") as f:
            data = json.load(f)
            campaigns = data if isinstance(data, list) else [data]
            for campaign in campaigns:
                tasks_data[campaign["campaign_id"]] = campaign
    web_dir = os.path.abspath(__file__ + "/../web")
    output_dir = os.path.abspath(args.output)
    
    env = os.environ.copy()
    env["OUTPUT_PATH"] = output_dir
    
    result = subprocess.run(["npm", "install"], cwd=web_dir, env=env)
    if result.returncode != 0:
        print("Failed to build frontend (install)")
        exit(1)
    result = subprocess.run(["npm", "run", "build"], cwd=web_dir, env=env)
    if result.returncode != 0:
        print("Failed to build frontend (build)")
        exit(1)
    
    for campaign_id, campaign in tasks_data.items():
        if campaign_id not in ext_progress:
            continue
            
        assignment = campaign["info"].get("assignment", "single-stream")
        virtual_sequence = []
        
        if assignment == "task-based":
            is_processed = isinstance(campaign["data"], dict)
            for user_i, (user_id, user_progress) in enumerate(ext_progress[campaign_id].items()):
                num_items = len(user_progress.get("progress", []))
                for item_i in range(num_items):
                    payload = campaign["data"][user_id][item_i] if is_processed else campaign["data"][user_i][item_i]
                    is_form = is_form_document(payload)
                    
                    items_existing = []
                    for row in ext_annotations.get(campaign_id, []):
                        if row.get("item_i") == item_i and row.get("user_id") == user_id:
                            items_existing.append(row)
                            
                    payload_existing = None
                    if items_existing:
                        latest_item = items_existing[-1]
                        payload_existing = {"annotation": latest_item["annotation"]}
                        if "comment" in latest_item:
                            payload_existing["comment"] = latest_item["comment"]
                            
                    virtual_sequence.append({
                        "payload": payload,
                        "payload_existing": payload_existing,
                        "is_form": is_form
                    })
        else:
            num_items = len(campaign.get("data", []))
            for item_i in range(num_items):
                payload = campaign["data"][item_i]
                is_form = is_form_document(payload)
                
                items_existing = []
                for row in ext_annotations.get(campaign_id, []):
                    if row.get("item_i") == item_i:
                        items_existing.append(row)
                        
                payload_existing = None
                if items_existing:
                    latest_item = items_existing[-1]
                    payload_existing = {"annotation": latest_item["annotation"]}
                    if "comment" in latest_item:
                        payload_existing["comment"] = latest_item["comment"]
                        
                virtual_sequence.append({
                    "payload": payload,
                    "payload_existing": payload_existing,
                    "is_form": is_form
                })
                
        num_virtual_items = len(virtual_sequence)
        virtual_progress = ["completed"] * num_virtual_items
        
        for i, item_data in enumerate(virtual_sequence):
            response_content = {
                "status": "form" if item_data["is_form"] else "ok",
                "time": 0,
                "progress": virtual_progress,
                "progress_welcome": [],
                "info": {
                    "item_i": i,
                    "instructions": _get_instructions(tasks_data, campaign_id),
                } | {
                    k: v
                    for k, v in campaign.get("info", {}).items()
                    if k in CAMPAIGN_INFO_PUBLIC
                },
                "payload": item_data["payload"],
            }
            if item_data["payload_existing"]:
                response_content["payload_existing"] = item_data["payload_existing"]
                
            out_path = os.path.join(output_dir, "api", campaign_id, f"{i}.json")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(response_content, f)

    import glob
    
    # Remove original index files
    for f in glob.glob(os.path.join(output_dir, "index.*")):
        if os.path.isfile(f):
            os.remove(f)
            
    # Rename annotate.* to index.*
    for f in glob.glob(os.path.join(output_dir, "annotate.*")):
        new_name = f.replace("annotate.", "index.")
        os.rename(f, new_name)
        
    # Update HTML references
    index_html_path = os.path.join(output_dir, "index.html")
    if os.path.exists(index_html_path):
        with open(index_html_path, "r") as f:
            content = f.read()
        content = content.replace("annotate.bundle.js", "index.bundle.js")
        with open(index_html_path, "w") as f:
            f.write(content)
            
    # Remove any other top-level HTML or JS files
    allowed_files = {"index.html", "index.bundle.js", "style.css", "favicon.svg"}
    for item in os.listdir(output_dir):
        item_path = os.path.join(output_dir, item)
        if os.path.isfile(item_path) and item not in allowed_files:
            os.remove(item_path)

    print(f"Baked annotations into a static site into {output_dir}")

"""
Command-line interface for managing and running the Pearmut server.
"""

import argparse
import hashlib
import json
import os
import urllib.parse

import psutil

from .utils import ROOT, load_progress_data, save_progress_data

os.makedirs(f"{ROOT}/data/tasks", exist_ok=True)
load_progress_data(warn=None)


def _run(args_unknown):
    import uvicorn

    from .app import app, tasks_data

    args = argparse.ArgumentParser()
    args.add_argument(
        "--port", type=int, default=8001, help="Port to run the server on"
    )
    args.add_argument(
        "--server",
        default="http://localhost:8001",
        help="Prefix server URL for protocol links",
    )
    args = args.parse_args(args_unknown)

    # print access dashboard URL for all campaigns
    if tasks_data:
        dashboard_url = (
            args.server
            + "/dashboard.html?"
            + "&".join(
                [
                    f"campaign_id={urllib.parse.quote_plus(campaign_id)}&token={campaign_data["token"]}"
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
    uvicorn.config.LOGGING_CONFIG["formatters"]["access"][
        "fmt"
    ] = "%(asctime)s %(levelprefix)s %(client_addr)s - %(request_line)s %(status_code)s"
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=args.port,
        reload=False,
    )


def _validate_item_structure(items):
    """
    Validate that items have the correct structure.
    Items should be lists of dictionaries with 'tgt' and optionally 'src' and/or 'ref' keys.
    The 'tgt' field should be a dictionary mapping model names to translations.

    Args:
        items: List of item dictionaries to validate
    """
    if not isinstance(items, list):
        raise ValueError("Items must be a list")

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each item must be a dictionary with 'tgt' key")
        if "tgt" not in item:
            raise ValueError("Each item must contain 'tgt' key")

        # Validate src is a string if present
        if "src" in item and not isinstance(item["src"], str):
            raise ValueError("Item 'src' must be a string")

        # Validate ref is a string if present
        if "ref" in item and not isinstance(item["ref"], str):
            raise ValueError("Item 'ref' must be a string")

        # Validate tgt is a dictionary (basic template with model names)
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
                    raise ValueError("Model names in 'tgt' dictionary must be strings")
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


def _add_single_campaign(campaign_data, overwrite, server):
    """
    Add a single campaign from campaign data dictionary.
    """
    import random

    import wonderwords

    if "campaign_id" not in campaign_data:
        raise ValueError("Campaign data must contain 'campaign_id' field.")
    if "info" not in campaign_data:
        raise ValueError("Campaign data must contain 'info' field.")
    if "data" not in campaign_data:
        raise ValueError("Campaign data must contain 'data' field.")

    with open(f"{ROOT}/data/progress.json", "r") as f:
        progress_data = json.load(f)

    if campaign_data["campaign_id"] in progress_data and not overwrite:
        raise ValueError(
            f"Campaign {campaign_data['campaign_id']} already exists.\n"
            "Use -o to overwrite."
        )

    if "assignment" not in campaign_data["info"]:
        raise ValueError("Campaign 'info' must contain 'assignment' field.")

    # Template defaults to "basic" if not specified
    assignment = campaign_data["info"]["assignment"]
    # use random words for identifying users
    rng = random.Random()
    rword = wonderwords.RandomWord(rng=rng)

    # Parse users specification from info
    users_spec = campaign_data["info"].get("users")
    user_tokens = {}  # user_id -> {"pass": ..., "fail": ...}

    if assignment == "task-based":
        tasks = campaign_data["data"]
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
        if users_spec is None:
            raise ValueError("Single-stream campaigns must specify 'users' in info.")
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
        if users_spec is None:
            raise ValueError("Dynamic campaigns must specify 'users' in info.")
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
        if "dynamic_top" not in campaign_data["info"]:
            campaign_data["info"]["dynamic_top"] = 2
        if "dynamic_first" not in campaign_data["info"]:
            campaign_data["info"]["dynamic_first"] = 5
        if "dynamic_contrastive_models" not in campaign_data["info"]:
            campaign_data["info"]["dynamic_contrastive_models"] = 1
        # Validate that dynamic_first is at least 1
        assert (
            campaign_data["info"]["dynamic_first"] >= 1
        ), "dynamic_first must be at least 1"
        # Validate that dynamic_contrastive_models is at most dynamic_top
        assert (
            campaign_data["info"]["dynamic_contrastive_models"]
            <= campaign_data["info"]["dynamic_top"]
        ), "dynamic_contrastive_models must be at most dynamic_top"
        # Validate that all items have the same models
        all_models = set()
        for item in campaign_data["data"]:
            if item and len(item) > 0:
                all_models.update(item[0]["tgt"].keys())
        for item in campaign_data["data"]:
            if item and len(item) > 0:
                item_models = set(item[0]["tgt"].keys())
                assert (
                    item_models == all_models
                ), "All items must have the same model outputs"
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
        campaign_data["info"]["protocol"] = "ESA"
        print(
            "Warning: 'protocol' not specified in campaign info. Defaulting to 'ESA'."
        )

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
        output_file = f"{ROOT}/data/outputs/{campaign_data['campaign_id']}.jsonl"
        if os.path.exists(output_file):
            os.remove(output_file)

    # For task-based, data is a dict mapping user_id -> tasks
    # For single-stream and dynamic, data is a flat list (shared among all users)
    if assignment == "task-based":
        campaign_data["data"] = {
            user_id: task for user_id, task in zip(user_ids, tasks)
        }
    elif assignment in ["single-stream", "dynamic"]:
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
            # TODO: progress tracking could be based on the assignment type
            "progress": (
                [False] * len(campaign_data["data"][user_id])
                if assignment == "task-based"
                else (
                    [False] * len(campaign_data["data"])
                    if assignment == "single-stream"
                    else (
                        [list() for _ in range(len(campaign_data["data"]))]
                        if assignment == "dynamic"
                        else []
                    )
                )
            ),
            "time_start": None,
            "time_end": None,
            "time": 0,
            "url": (
                f"{campaign_data['info'].get("template", "basic")}.html"
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
                with open(f"{ROOT}/data/tasks/{other_campaign_id}.json", "r") as f:
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
    with open(f"{ROOT}/data/tasks/{campaign_data['campaign_id']}.json", "w") as f:
        json.dump(campaign_data, f, indent=2, ensure_ascii=False)

    progress_data[campaign_data["campaign_id"]] = user_progress
    save_progress_data(progress_data)

    print(
        "🎛️ ",
        f"{server}/dashboard.html"
        f"?campaign_id={urllib.parse.quote_plus(campaign_data['campaign_id'])}"
        f"&token={campaign_data['token']}",
    )
    for user_id, user_val in user_progress.items():
        # point to the protocol URL
        print(f'🧑 {server}/{user_val["url"]}')
    print()


def _add_campaign(args_unknown):
    """
    Add campaigns from one or more JSON data files.
    """
    args = argparse.ArgumentParser()
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
        "--server",
        default="http://localhost:8001",
        help="Prefix server URL for protocol links",
    )
    args = args.parse_args(args_unknown)

    for data_file in args.data_files:
        try:
            with open(data_file, "r") as f:
                _add_single_campaign(json.load(f), args.overwrite, args.server)
        except Exception as e:
            print(f"Error processing {data_file}: {e}")
            exit(1)


def main():
    """
    Main entry point for the CLI.
    """
    args = argparse.ArgumentParser()
    args.add_argument(
        "command",
        type=str,
        choices=["run", "add", "purge"],
        default="run",
        nargs="?",
    )
    args, args_unknown = args.parse_known_args()

    # enforce that only one pearmut process is running
    for p in psutil.process_iter():
        if "pearmut" == p.name() and p.pid != os.getpid():
            print("Exit all running pearmut processes before running more commands.")
            print(p)
            exit(1)

    if args.command == "run":
        _run(args_unknown)
    elif args.command == "add":
        _add_campaign(args_unknown)
    elif args.command == "purge":
        import shutil

        def _unlink_assets(campaign_id):
            """Unlink assets symlink for a campaign if it exists."""
            task_file = f"{ROOT}/data/tasks/{campaign_id}.json"
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
                task_file = f"{ROOT}/data/tasks/{campaign_id}.json"
                if os.path.exists(task_file):
                    os.remove(task_file)
                # Remove output file
                output_file = f"{ROOT}/data/outputs/{campaign_id}.jsonl"
                if os.path.exists(output_file):
                    os.remove(output_file)
                # Remove from progress data
                progress_data = load_progress_data()
                if campaign_id in progress_data:
                    del progress_data[campaign_id]
                    save_progress_data(progress_data)
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
                shutil.rmtree(f"{ROOT}/data/tasks", ignore_errors=True)
                shutil.rmtree(f"{ROOT}/data/outputs", ignore_errors=True)
                if os.path.exists(f"{ROOT}/data/progress.json"):
                    os.remove(f"{ROOT}/data/progress.json")
                print("All campaign data purged.")
            else:
                print("Cancelled.")

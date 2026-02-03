import json
import os
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .assignment import get_i_item, get_next_item, reset_task, update_progress
from .results_export import (
    compute_model_scores,
    generate_latex_table,
    generate_pdf,
    generate_typst_table,
)
from .utils import (
    RESET_MARKER,
    ROOT,
    TOKEN_MAIN,
    check_validation_threshold,
    get_db_log,
    load_progress_data,
    save_db_payload,
    save_progress_data,
)

os.makedirs(f"{ROOT}/data/outputs", exist_ok=True)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tasks_data = {}
progress_data = load_progress_data(
    warn="No progress.json found. Running, but no campaign will be available."
)

# load all tasks into data_all
for campaign_id in progress_data.keys():
    with open(f"{ROOT}/data/tasks/{campaign_id}.json", "r") as f:
        tasks_data[campaign_id] = json.load(f)


class LogResponseRequest(BaseModel):
    campaign_id: str
    user_id: str
    item_i: int | str
    payload: dict[str, Any]


@app.post("/log-response")
async def _log_response(request: LogResponseRequest):
    global progress_data

    campaign_id = request.campaign_id
    user_id = request.user_id
    item_i = request.item_i

    if campaign_id not in progress_data:
        return JSONResponse(content="Unknown campaign ID", status_code=400)
    if user_id not in progress_data[campaign_id]:
        return JSONResponse(content="Unknown user ID", status_code=400)

    # append response to the output log
    save_db_payload(
        campaign_id, request.payload | {"user_id": user_id, "item_i": item_i}
    )

    # if actions were submitted, we can log time data
    if "actions" in request.payload:
        times = [x["time"] for x in request.payload["actions"]]
        if progress_data[campaign_id][user_id]["time_start"] is None:
            progress_data[campaign_id][user_id]["time_start"] = min(times)
        progress_data[campaign_id][user_id]["time_end"] = max(times)
        progress_data[campaign_id][user_id]["time"] += sum(
            [min(b - a, 60) for a, b in zip(times, times[1:])]
        )

    # Initialize validation_checks if it doesn't exist
    if "validations" in request.payload:
        if "validations" not in progress_data[campaign_id][user_id]:
            progress_data[campaign_id][user_id]["validations"] = {}

        progress_data[campaign_id][user_id]["validations"][request.item_i] = (
            request.payload["validations"]
        )

    update_progress(
        campaign_id, user_id, tasks_data, progress_data, request.item_i, request.payload
    )
    save_progress_data(progress_data)

    return JSONResponse(content="ok", status_code=200)


class NextItemRequest(BaseModel):
    campaign_id: str
    user_id: str


@app.post("/get-next-item")
async def _get_next_item(request: NextItemRequest):
    campaign_id = request.campaign_id
    user_id = request.user_id

    if campaign_id not in progress_data:
        return JSONResponse(content="Unknown campaign ID", status_code=400)
    if user_id not in progress_data[campaign_id]:
        return JSONResponse(content="Unknown user ID", status_code=400)

    return get_next_item(
        campaign_id,
        user_id,
        tasks_data,
        progress_data,
    )


class GetItemRequest(BaseModel):
    campaign_id: str
    user_id: str
    item_i: int | str


@app.post("/get-i-item")
async def _get_i_item(request: GetItemRequest):
    campaign_id = request.campaign_id
    user_id = request.user_id
    item_i = request.item_i

    if campaign_id not in progress_data:
        return JSONResponse(content="Unknown campaign ID", status_code=400)
    if user_id not in progress_data[campaign_id]:
        return JSONResponse(content="Unknown user ID", status_code=400)

    return get_i_item(
        campaign_id,
        user_id,
        tasks_data,
        progress_data,
        item_i,
    )


class DashboardDataRequest(BaseModel):
    campaign_id: str
    token: str | None = None


@app.post("/dashboard-data")
async def _dashboard_data(request: DashboardDataRequest):
    campaign_id = request.campaign_id

    if campaign_id not in progress_data:
        return JSONResponse(content="Unknown campaign ID", status_code=400)

    is_privileged = request.token == tasks_data[campaign_id]["token"]

    progress_new = {}
    assignment = tasks_data[campaign_id]["info"]["assignment"]
    if assignment not in ["task-based", "single-stream", "dynamic"]:
        return JSONResponse(
            content="Unsupported campaign assignment type", status_code=400
        )

    # Get threshold info for the campaign
    validation_threshold = tasks_data[campaign_id]["info"].get("validation_threshold")

    # For single-stream and dynamic, calculate user-specific and global progress
    user_finished_counts = {}
    global_progress_count = 0
    
    if assignment in ["single-stream", "dynamic"]:
        # Get all annotations from the database
        annotations = get_db_log(campaign_id)
        
        # Build user_items and global_items, respecting reset markers
        # For each (user_id, item_i) pair, track the index of the last reset marker
        user_item_last_reset_index = {}  # (user_id, item_i) -> last_reset_index
        for idx, entry in enumerate(annotations):
            if entry.get("annotation") == RESET_MARKER:
                user_id_entry = entry.get("user_id")
                item_i_entry = entry.get("item_i")
                if user_id_entry and item_i_entry is not None:
                    user_item_last_reset_index[(user_id_entry, item_i_entry)] = idx
        
        # Count unique items each user has annotated (excluding welcome items and respecting resets)
        for user_id in progress_data[campaign_id].keys():
            user_items = set()
            for idx, entry in enumerate(annotations):
                entry_user_id = entry.get("user_id")
                entry_item_i = entry.get("item_i")
                
                if (
                    entry_user_id == user_id
                    and entry.get("annotation") != RESET_MARKER
                    and entry_item_i is not None
                    and not isinstance(entry_item_i, str)  # Exclude welcome items
                ):
                    # Only count if this entry is after the last reset for this (user, item) pair
                    reset_idx = user_item_last_reset_index.get((user_id, entry_item_i), -1)
                    if idx > reset_idx:
                        user_items.add(entry_item_i)
            user_finished_counts[user_id] = len(user_items)
        
        # Count global progress: unique items that have at least one annotation (respecting resets)
        # For global, an item is counted if ANY user has annotated it after their last reset
        global_items = set()
        for idx, entry in enumerate(annotations):
            entry_user_id = entry.get("user_id")
            entry_item_i = entry.get("item_i")
            
            if (
                entry.get("annotation") != RESET_MARKER
                and entry_item_i is not None
                and not isinstance(entry_item_i, str)  # Exclude welcome items
            ):
                # Only count if this entry is after the last reset for this (user, item) pair
                reset_idx = user_item_last_reset_index.get((entry_user_id, entry_item_i), -1)
                if idx > reset_idx:
                    global_items.add(entry_item_i)
        global_progress_count = len(global_items)

    for user_id, user_val in progress_data[campaign_id].items():
        # shallow copy
        entry = dict(user_val)
        entry["validations"] = [
            all(v) for v in list(entry.get("validations", {}).values())
        ]

        # Add threshold pass/fail status (only when user is complete)
        if all(entry["progress"]):
            entry["threshold_passed"] = check_validation_threshold(
                tasks_data, progress_data, campaign_id, user_id
            )
        else:
            entry["threshold_passed"] = None

        if not is_privileged:
            entry["token_correct"] = None
            entry["token_incorrect"] = None

        # Add user-specific progress counts for single-stream and dynamic
        if assignment in ["single-stream", "dynamic"]:
            entry["finished_by_user"] = user_finished_counts.get(user_id, 0)
            entry["global_progress"] = global_progress_count

        progress_new[user_id] = entry

    return JSONResponse(
        content={
            "data": progress_new,
            "validation_threshold": validation_threshold,
            "assignment": assignment,
        },
        status_code=200,
    )


class DashboardResultsRequest(BaseModel):
    campaign_id: str
    token: str


@app.post("/dashboard-results")
async def _dashboard_results(request: DashboardResultsRequest):
    campaign_id = request.campaign_id
    token = request.token

    if campaign_id not in progress_data:
        return JSONResponse(content="Unknown campaign ID", status_code=400)

    # Check if token is valid
    if token != tasks_data[campaign_id]["token"]:
        return JSONResponse(content="Invalid token", status_code=400)

    results = compute_model_scores(campaign_id)
    return JSONResponse(content=results, status_code=200)


@app.get("/export-results")
async def _export_results(
    campaign_id: str = Query(),
    token: str = Query(),
    format: str = Query(),
):
    if campaign_id not in progress_data:
        return JSONResponse(content="Unknown campaign ID", status_code=400)

    # Check if token is valid
    if token != tasks_data[campaign_id]["token"]:
        return JSONResponse(content="Invalid token", status_code=400)

    results = compute_model_scores(campaign_id)

    if format == "typst":
        content = generate_typst_table(results)
        return Response(
            content=content,
            media_type="text/plain",
        )
    elif format == "latex":
        content = generate_latex_table(results)
        return Response(
            content=content,
            media_type="text/plain",
        )
    elif format == "pdf":
        pdf_bytes = generate_pdf(results, campaign_id)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
        )
    else:
        return JSONResponse(content="Invalid export format", status_code=400)


class ResetTaskRequest(BaseModel):
    campaign_id: str
    user_id: str
    token: str


@app.post("/reset-task")
async def _reset_task(request: ResetTaskRequest):
    # ruff: noqa: F841
    campaign_id = request.campaign_id
    user_id = request.user_id
    token = request.token

    if campaign_id not in progress_data:
        return JSONResponse(content="Unknown campaign ID", status_code=400)
    if token != tasks_data[campaign_id]["token"]:
        return JSONResponse(content="Invalid token", status_code=400)
    if user_id not in progress_data[campaign_id]:
        return JSONResponse(content="Unknown user ID", status_code=400)

    response = reset_task(campaign_id, user_id, tasks_data, progress_data)
    save_progress_data(progress_data)
    return response


class PurgeCampaignRequest(BaseModel):
    campaign_id: str
    token: str


@app.post("/purge-campaign")
async def _purge_campaign(request: PurgeCampaignRequest):
    global progress_data, tasks_data

    campaign_id = request.campaign_id
    token = request.token

    if campaign_id not in progress_data:
        return JSONResponse(content="Unknown campaign ID", status_code=400)
    if token != tasks_data[campaign_id]["token"]:
        return JSONResponse(content="Invalid token", status_code=400)

    # Unlink assets if they exist
    destination = (
        tasks_data[campaign_id].get("info", {}).get("assets", {}).get("destination")
    )
    if destination:
        symlink_path = f"{ROOT}/data/{destination}".rstrip("/")
        if os.path.islink(symlink_path):
            os.remove(symlink_path)

    # Remove task file
    task_file = f"{ROOT}/data/tasks/{campaign_id}.json"
    if os.path.exists(task_file):
        os.remove(task_file)

    # Remove output file
    output_file = f"{ROOT}/data/outputs/{campaign_id}.jsonl"
    if os.path.exists(output_file):
        os.remove(output_file)

    # Remove from in-memory data structures
    del tasks_data[campaign_id]
    del progress_data[campaign_id]

    # Save updated progress data
    save_progress_data(progress_data)

    return JSONResponse(content="ok", status_code=200)


class AddCampaignRequest(BaseModel):
    campaign_data: dict[str, Any]
    token_main: str


@app.post("/add-campaign")
async def _add_campaign(request: AddCampaignRequest):
    global progress_data, tasks_data

    from .cli import _add_single_campaign

    if request.token_main != TOKEN_MAIN:
        return JSONResponse(
            content={"error": "Invalid main token. Use the latest one."},
            status_code=400,
        )

    try:
        server = f"{os.environ.get('PEARMUT_SERVER_URL', 'http://localhost:8001')}"
        _add_single_campaign(request.campaign_data, overwrite=False, server=server)

        campaign_id = request.campaign_data["campaign_id"]
        with open(f"{ROOT}/data/tasks/{campaign_id}.json", "r") as f:
            tasks_data[campaign_id] = json.load(f)

        progress_data = load_progress_data(warn=None)

        return JSONResponse(
            content={
                "status": "ok",
                "campaign_id": campaign_id,
                "token": tasks_data[campaign_id]["token"],
            },
            status_code=200,
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)


@app.get("/download-annotations")
async def _download_annotations(
    campaign_id: list[str] = Query(),
    # NOTE: currently not checking tokens for progress download as it is non-destructive
    # token: list[str] = Query()
):
    output = {}
    for campaign_id in campaign_id:
        output_path = f"{ROOT}/data/outputs/{campaign_id}.jsonl"
        if campaign_id not in progress_data:
            return JSONResponse(
                content=f"Unknown campaign ID {campaign_id}", status_code=400
            )
        if not os.path.exists(output_path):
            output[campaign_id] = []
        else:
            with open(output_path, "r") as f:
                output[campaign_id] = [json.loads(x) for x in f.readlines()]

    return JSONResponse(
        content=output,
        status_code=200,
        headers={
            "Content-Disposition": 'attachment; filename="annotations.json"',
        },
    )


@app.get("/download-progress")
async def _download_progress(
    campaign_id: list[str] = Query(), token: list[str] = Query()
):
    if len(campaign_id) != len(token):
        return JSONResponse(
            content="Mismatched campaign_id and token count", status_code=400
        )

    output = {}
    for i, cid in enumerate(campaign_id):
        if cid not in progress_data:
            return JSONResponse(content=f"Unknown campaign ID {cid}", status_code=400)
        if token[i] != tasks_data[cid]["token"]:
            return JSONResponse(
                content=f"Invalid token for campaign ID {cid}", status_code=400
            )

        output[cid] = progress_data[cid]

    return JSONResponse(
        content=output,
        status_code=200,
        headers={
            "Content-Disposition": 'attachment; filename="progress.json"',
        },
    )


static_dir = f"{os.path.dirname(os.path.abspath(__file__))}/static/"
if not os.path.exists(static_dir + "index.html"):
    raise FileNotFoundError(
        "Static directory not found. Please build the frontend first."
    )


# Serve HTML files directly without redirect
@app.get("/annotate")
async def serve_annotate():
    return FileResponse(static_dir + "annotate.html")


@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse(static_dir + "dashboard.html")


# Mount user assets from data/assets/
assets_dir = f"{ROOT}/data/assets"
os.makedirs(assets_dir, exist_ok=True)

app.mount(
    "/assets",
    StaticFiles(directory=assets_dir, follow_symlink=True),
    name="assets",
)

app.mount(
    "/",
    StaticFiles(directory=static_dir, html=True, follow_symlink=True),
    name="static",
)

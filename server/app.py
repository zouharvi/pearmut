import json
import os
from itertools import pairwise
from typing import Annotated, Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .assignment import get_i_item, get_next_item, reset_campaign, update_progress
from .results_export import (
    compute_model_scores,
    generate_latex_table,
    generate_pdf,
    generate_typst_table,
)
from .utils import (
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

campaigns_data = {}
progress_data = load_progress_data(
    warn="No progress files found. Running, but no campaign will be available."
)


def _validate_campaign_id(campaign_id: str) -> str:
    if not campaign_id or campaign_id in {".", ".."}:
        raise ValueError("Invalid campaign ID")
    if os.path.sep in campaign_id or (os.path.altsep and os.path.altsep in campaign_id):
        raise ValueError("Invalid campaign ID")
    return campaign_id


def _campaign_json_path(campaign_id: str) -> str:
    return f"{ROOT}/data/campaigns/{_validate_campaign_id(campaign_id)}.json"


# load all tasks into data_all
for campaign_id in progress_data:
    with open(_campaign_json_path(campaign_id), "r") as f:
        campaigns_data[campaign_id] = json.load(f)


class LogResponseRequest(BaseModel):
    campaign_id: str
    user_id: str
    item_i: int | str
    payload: dict[str, Any]


@app.post("/log-response")
async def _log_response(request: LogResponseRequest):
    campaign_id = request.campaign_id
    user_id = request.user_id
    item_i = request.item_i

    if campaign_id not in progress_data:
        return JSONResponse(content="Unknown campaign ID. Maybe it was removed?", status_code=400)
    if user_id not in progress_data[campaign_id]:
        return JSONResponse(content="Unknown user ID. Maybe the campaign was restarted?", status_code=400)

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
        # use one "minute" as the maximum time between actions to avoid logging long pauses
        progress_data[campaign_id][user_id]["time"] += sum(
            min(b - a, 61) for a, b in pairwise(times)
        )

    # Initialize validation_checks if it doesn't exist
    if "validations" in request.payload:
        if "validations" not in progress_data[campaign_id][user_id]:
            progress_data[campaign_id][user_id]["validations"] = {}

        progress_data[campaign_id][user_id]["validations"][request.item_i] = (
            request.payload["validations"]
        )

    update_progress(
        campaign_id, user_id, campaigns_data, progress_data, request.item_i, request.payload
    )
    save_progress_data(campaign_id, progress_data[campaign_id])

    return JSONResponse(content="ok", status_code=200)


class NextItemRequest(BaseModel):
    campaign_id: str
    user_id: str


@app.post("/get-next-item")
async def _get_next_item(request: NextItemRequest):
    campaign_id = request.campaign_id
    user_id = request.user_id

    if campaign_id not in progress_data:
        return JSONResponse(content="Unknown campaign ID. Maybe it was removed?", status_code=400)
    if user_id not in progress_data[campaign_id]:
        return JSONResponse(content="Unknown user ID. Maybe the campaign was restarted?", status_code=400)

    return get_next_item(
        campaign_id,
        user_id,
        campaigns_data,
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
        return JSONResponse(content="Unknown campaign ID. Maybe it was removed?", status_code=400)
    if user_id not in progress_data[campaign_id]:
        return JSONResponse(content="Unknown user ID. Maybe the campaign was restarted?", status_code=400)

    return get_i_item(
        campaign_id,
        user_id,
        campaigns_data,
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
        return JSONResponse(content="Unknown campaign ID. Maybe it was removed?", status_code=400)

    is_privileged = request.token == campaigns_data[campaign_id]["token"]

    progress_new = {}
    assignment = campaigns_data[campaign_id]["info"]["assignment"]
    if assignment not in ["task-based", "single-stream", "dynamic"]:
        return JSONResponse(
            content="Unsupported campaign assignment type", status_code=400
        )

    # Get threshold info for the campaign
    validation_threshold = campaigns_data[campaign_id]["info"].get("validation_threshold")

    for user_id, user_val in progress_data[campaign_id].items():
        # shallow copy
        entry = dict(user_val)
        entry["validations"] = [
            all(v) for v in list(entry.get("validations", {}).values())
        ]

        # Add threshold pass/fail status (only when user is complete)
        if (
            campaigns_data[campaign_id]["info"]["assignment"] != "dynamic"
            and all(v in {"completed", "completed_foreign"} for v in entry["progress"])
        ) or (
            campaigns_data[campaign_id]["info"]["assignment"] == "dynamic"
            and all(
                v in {"completed", "completed_foreign"}
                for mv in entry["progress"]
                for v in mv.values()
            )
        ):
            entry["threshold_passed"] = check_validation_threshold(
                campaigns_data, progress_data, campaign_id, user_id
            )
        else:
            entry["threshold_passed"] = None

        if not is_privileged:
            entry["token_correct"] = None
            entry["token_incorrect"] = None

        progress_new[user_id] = entry

    return JSONResponse(
        content={
            "data": progress_new,
            "validation_threshold": validation_threshold,
            "assignment": assignment,
            "docs_per_user": campaigns_data[campaign_id]["info"].get("docs_per_user"),
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
        return JSONResponse(content="Unknown campaign ID. Maybe it was removed?", status_code=400)

    # Check if token is valid
    if token != campaigns_data[campaign_id]["token"]:
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
        return JSONResponse(content="Unknown campaign ID. Maybe it was removed?", status_code=400)

    # Check if token is valid
    if token != campaigns_data[campaign_id]["token"]:
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


@app.post("/reset-campaign")
async def _reset_campaign(request: ResetTaskRequest):
    campaign_id = request.campaign_id
    user_id = request.user_id
    token = request.token

    if campaign_id not in progress_data:
        return JSONResponse(content="Unknown campaign ID. Maybe it was removed?", status_code=400)
    if token != campaigns_data[campaign_id]["token"]:
        return JSONResponse(content="Invalid token", status_code=400)
    if user_id not in progress_data[campaign_id]:
        return JSONResponse(content="Unknown user ID. Maybe the campaign was restarted?", status_code=400)

    response = reset_campaign(campaign_id, user_id, campaigns_data, progress_data)
    save_progress_data(campaign_id, progress_data[campaign_id])
    return response


class PurgeCampaignRequest(BaseModel):
    campaign_id: str
    token: str


@app.post("/purge-campaign")
async def _purge_campaign(request: PurgeCampaignRequest):
    campaign_id = request.campaign_id
    token = request.token

    if campaign_id not in progress_data:
        return JSONResponse(content="Unknown campaign ID. Maybe it was removed?", status_code=400)
    if token != campaigns_data[campaign_id]["token"]:
        return JSONResponse(content="Invalid token", status_code=400)

    # Unlink assets if they exist
    destination = (
        campaigns_data[campaign_id].get("info", {}).get("assets", {}).get("destination")
    )
    if destination:
        symlink_path = f"{ROOT}/data/{destination}".rstrip("/")
        if os.path.islink(symlink_path):
            os.remove(symlink_path)

    # Remove task file
    task_file = f"{ROOT}/data/campaigns/{campaign_id}.json"
    if os.path.exists(task_file):
        os.remove(task_file)

    # Remove output file
    output_file = f"{ROOT}/data/annotations/{campaign_id}.jsonl"
    if os.path.exists(output_file):
        os.remove(output_file)

    # Remove from in-memory data structures
    del campaigns_data[campaign_id]
    del progress_data[campaign_id]

    # Remove progress file
    progress_file = f"{ROOT}/data/progress/{campaign_id}.json"
    if os.path.exists(progress_file):
        os.remove(progress_file)

    return JSONResponse(content="ok", status_code=200)


class AddCampaignRequest(BaseModel):
    campaign_data: dict[str, Any] | list[dict[str, Any]]
    token_main: str


@app.post("/add-campaign")
def _add_campaign(request: AddCampaignRequest):
    global progress_data

    from .cli import _add_single_campaign

    if request.token_main != TOKEN_MAIN:
        return JSONResponse(
            content={"error": "Invalid main token. Use the latest one."},
            status_code=400,
        )

    try:
        if isinstance(request.campaign_data, list):
            campaigns = request.campaign_data
        else:
            campaigns = [request.campaign_data]

        added_campaigns = []
        for campaign_data in campaigns:
            _add_single_campaign(campaign_data, overwrite=False, url=None)

            campaign_id = campaign_data["campaign_id"]
            _validate_campaign_id(campaign_id)
            campaigns_data[campaign_id] = campaign_data
            
            added_campaigns.append(
                {"campaign_id": campaign_id, "token": campaigns_data[campaign_id]["token"]}
            )

        progress_data = load_progress_data(warn=None)

        return JSONResponse(
            content={
                "status": "ok",
                "campaigns": added_campaigns,
            },
            status_code=200,
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return JSONResponse(content={"error": "Failed to add campaign data."}, status_code=400)


@app.get("/download-annotations")
def _download_annotations(
    campaign_id: Annotated[list[str], Query()],
    filename: Annotated[str, Query()] = "annotations.json",
    # NOTE: currently not checking tokens for progress download as it is non-destructive
    # token: list[str] = Query()
):
    output = {}
    for cid in campaign_id:
        try:
            _validate_campaign_id(cid)
        except ValueError:
            return JSONResponse(content=f"Invalid campaign ID. {cid}", status_code=400)
        if cid not in progress_data:
            return JSONResponse(
                content=f"Unknown campaign ID. Maybe it was removed? {cid}", status_code=400
            )
        output[cid] = get_db_log(cid)

    if not filename.endswith(".json"):
        filename += ".json"

    return JSONResponse(
        content=output,
        status_code=200,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@app.get("/download-campaigns")
def _download_campaigns(
    campaign_id: Annotated[list[str], Query()],
    filename: Annotated[str, Query()] = "campaigns.json",
    # NOTE: currently not checking tokens for campaigns download as it is non-destructive
):
    output = []
    for cid in campaign_id:
        try:
            _validate_campaign_id(cid)
        except ValueError:
            return JSONResponse(content=f"Invalid campaign ID. {cid}", status_code=400)
        if cid not in progress_data:
            return JSONResponse(
                content=f"Unknown campaign ID. Maybe it was removed? {cid}", status_code=400
            )
        if cid in campaigns_data:
            output.append(campaigns_data[cid])

    if not filename.endswith(".json"):
        filename += ".json"

    return JSONResponse(
        content=output,
        status_code=200,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )



@app.get("/download-progress")
async def _download_progress(
    campaign_id: Annotated[list[str], Query()],
    token: Annotated[list[str], Query()],
    filename: Annotated[str, Query()] = "progress.json",
):
    if len(campaign_id) != len(token):
        return JSONResponse(
            content="Mismatched campaign_id and token count", status_code=400
        )

    output = {}
    for i, cid in enumerate(campaign_id):
        if cid not in progress_data:
            return JSONResponse(content=f"Unknown campaign ID. Maybe it was removed? {cid}", status_code=400)
        if token[i] != campaigns_data[cid]["token"]:
            return JSONResponse(
                content=f"Invalid token for campaign ID {cid}", status_code=400
            )

        output[cid] = progress_data[cid]

    if not filename.endswith(".json"):
        filename += ".json"

    return JSONResponse(
        content=output,
        status_code=200,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
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

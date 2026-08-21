import './style.css';
import { notify, computeProgressString } from "./utils"
import $ from 'jquery';

let searchParams = new URLSearchParams(window.location.search)

let campaign_ids = searchParams.getAll("campaign_id")
let tokens = searchParams.getAll("token")
let tokenMain = searchParams.get("token_main") || ""

// verify that tokens length is either 0 or same as campaign_ids length
if (tokens.length != 0 && tokens.length != campaign_ids.length) {
    $("#main_div").html(`
        <div class="white-box">
        ⛔ Either no tokens should be provided or the same number as campaign IDs.
        </div>
    `)
    throw new Error("Mismatched number of tokens and campaign IDs")
}

function delta_to_human(delta: number, no_days: boolean): string {
    /* Convert a time delta in seconds to a human-readable format */
    if (delta < 60) {
        return `${Math.round(delta)}s`
    } else if (delta < 60 * 60) {
        return `${Math.round(delta / 60)}m`
    } else if (delta < 60 * 60 * 24 || no_days) {
        return `${Math.round(delta / 60 / 60)}h`
    } else {
        return `${Math.round(delta / 60 / 60 / 24)}d`
    }
}

async function fetchAndRenderCampaign(campaign_id: string, token: string | null) {
    let campaign = await $.ajax({
        url: `dashboard-data`,
        method: "POST",
        data: JSON.stringify({ "campaign_id": campaign_id, "token": token }),
        contentType: "application/json",
        dataType: "json",
    });
    let data = campaign.data;
    let assignment = campaign.assignment;

    let html = ""
    html += `
    <table class="dashboard-table">
        <thead><tr>
            <th style="min-width: 300px;">User</th>
            <th style="min-width: 100px;">Progress</th>
            <th style="min-width: 80px;">First</th>
            <th style="min-width: 80px;">Last</th>
            <th style="min-width: 80px;" title="Idle at most 1 minute between actions (click, mouse movement, ...)">Active time</th>
            <th style="min-width: 70px;">Checks</th>
            <th style="min-width: 50px;">Actions</th>
        </tr></thead>
        <tbody>`
    for (let user_id in data) {
        const progress = data[user_id]["progress"] as Array<string | object>
        const progressResult = computeProgressString(
            progress, assignment, campaign.dynamic_models, campaign.docs_per_user,
            data[user_id]["progress_welcome"] as Array<boolean> | undefined, data[user_id]["progress_goodbye"] as Array<boolean> | undefined
        );
        let progress_display = progressResult.display;

        // Calculate total for status determination
        let total_count = progressResult.total_count;
        let total_total = progressResult.total_total;

        let threshold_passed = data[user_id]["threshold_passed"]
        let status = ''
        if (data[user_id]["time"] == 0)
            status = '💤'
        else if (data[user_id]["time"] != 0 && (total_count == total_total || threshold_passed !== null)) {
            // Use threshold_passed to determine if user passed/failed
            // threshold_passed is null if not complete, true if passed, false if failed
            if (threshold_passed === false)
                status = '❌'
            else
                status = '✅'
        }
        else
            status = '✍️'

        html += '<tr>'

        // user id and emoji
        let display_name = data[user_id]["note"] ? data[user_id]["note"] : user_id;
        html += `<td>${status} <span class="edit-note" user_id="${user_id}" current_note="${data[user_id]["note"] || ''}" style="cursor: pointer;" title="Click to edit name for ${user_id}">${display_name}</span></td>`

        // time section - show separate progress
        html += `<td>${progress_display}</td>`
        if (data[user_id]["time_start"] == null) {
            html += `<td title="N/A"></td>`
        } else {
            html += `<td title="${new Date(data[user_id]["time_start"] * 1000).toLocaleString()}">${delta_to_human(Date.now() / 1000 - data[user_id]["time_start"], false)} ago</td>`
        }
        if (data[user_id]["time_end"] == null) {
            html += `<td title="N/A"></td>`
        } else {
            html += `<td title="${new Date(data[user_id]["time_end"] * 1000).toLocaleString()}">${delta_to_human(Date.now() / 1000 - data[user_id]["time_end"], false)} ago</td>`
        }
        html += `<td title="Active time; idle at most 1 minute (click, mouse movement, ...)">${Math.round(data[user_id]["time"] / 60)}m</td>`

        let validation_passed = data[user_id]["validations"].reduce((a: number, b: boolean) => a + (b ? 1 : 0), 0)
        let validation_total = data[user_id]["validations"].length
        html += `<td><span style="${validation_passed != validation_total ? 'color: #c75050;' : ''}">${validation_passed}</span><span style="color: #333;">/${validation_total}</span></td>`

        // actions section
        html += `<td>
            <a href="${data[user_id]["url"]}">🔗</a>
            &nbsp;&nbsp;
            <a href="${data[user_id]["url"]}&frozen" title="View only (frozen)">👁️</a>
            &nbsp;&nbsp;
            <span class="reset-campaign" user_id="${user_id}" ${token == null ? "disabled" : ""}>🗑️</span>
            </td>
        </tr>
        `
    }
    html += '</tbody></table>'

    // link to campaign-specific dashboard
    let dashboard_url = `dashboard?campaign_id=${encodeURIComponent(campaign_id)}${token != null ? `&token=${encodeURIComponent(token)}` : ''}`

    let campaign_progress = 0;
    let campaign_total = 0;
    let campaign_time = 0;
    let user_ids = Object.keys(data);
    
    if (user_ids.length > 0) {
        for (let user_id of user_ids) {
            campaign_time += data[user_id]["time"] || 0;
        }
        if (assignment === "task-based") {
            for (let user_id of user_ids) {
                const progress = data[user_id]["progress"] as Array<string>;
                campaign_progress += progress.filter(v => v === "completed").length;
                campaign_total += progress.length;
            }
        } else if (assignment === "single-stream") {
            const first_progress = data[user_ids[0]]["progress"] as Array<string>;
            campaign_total = first_progress.length;
            for (let user_id of user_ids) {
                const progress = data[user_id]["progress"] as Array<string>;
                campaign_progress += progress.filter(v => v === "completed").length;
            }
        } else if (assignment === "dynamic") {
            const first_progress = data[user_ids[0]]["progress"] as Array<any>;
            campaign_total = 0;
            
            for (let i = 0; i < first_progress.length; i++) {
                let models = Object.keys(first_progress[i]);
                campaign_total += models.length;
                for (let model of models) {
                    let model_annotated = false;
                    for (let user_id of user_ids) {
                        const progress = data[user_id]["progress"] as Array<any>;
                        if (progress[i] && progress[i][model] === "completed") {
                            model_annotated = true;
                            break;
                        }
                    }
                    if (model_annotated) {
                        campaign_progress++;
                    }
                }
            }
        }
    }

    let el = $(`
        <div class="white-box" style="display: flex; gap: 20px; min-width: 1000px;">
            <div>
                <h3 style="margin: 0; padding-bottom: 5px;">
                ${campaign_id} 
                <span style="font-weight: normal; font-size: 0.8em; color: #666; margin-left: 5px;" title="Campaign progress (regular items)">${campaign_progress}/${campaign_total}</span>
                <span style="font-weight: normal; font-size: 0.8em; color: #666; margin-left: 5px;" title="Active time; idle at most 1 minute (click, mouse movement, ...)">${delta_to_human(campaign_time, true)}</span>
                <span style="float: right; margin-right: 20px;">
                    ${(token !== null && (assignment === "single-stream" || assignment === "dynamic")) ? '<a class="add-user-btn" style="cursor: pointer;" title="Add new user">🧑</a>' : ''}
                    &nbsp;
                    <a href="${dashboard_url}" title="Link to dashboard">🔗</a>&nbsp;
                    <a class="show-ranking-btn" style="cursor: pointer; opacity: 1;" title="Show ranking">⚖️</a>&nbsp;
                    ${token !== null ? '&nbsp;<a class="purge-campaign-btn" style="cursor: pointer;" title="Purge/reset campaign">🗑️</a>' : ''}
                </span>
                </h3>
                <div class="dashboard-content">
                    ${html}
                </div>
            </div>
            <div class="ranking-content" style="display: none; padding-top: 29px;">
            </div>
        </div>
        <br>
        `)

    $("#dashboard_div").append(el)

    // Add event listener for show/hide ranking button
    el.find(".show-ranking-btn").on("click", async function () {
        const $content = el.find(".ranking-content");

        if ($content.is(":visible")) {
            $content.hide();
            $(this).css("opacity", "1");
            return;
        }

        $(this).css("opacity", "0.5");

        // Check if data is already loaded
        if ($content.children().length > 0) {
            $content.show();
            return;
        }

        // Fetch results data
        try {
            const resultsData = await $.ajax({
                url: `dashboard-results`,
                method: "POST",
                data: JSON.stringify({ "campaign_id": campaign_id, "token": token }),
                contentType: "application/json",
                dataType: "json",
            });

            if (resultsData && resultsData.length > 0) {
                let tableHtml = `
                    <table class="results-table">
                        <thead><tr>
                            <th style="min-width: 200px;">Model</th>
                            <th>Score</th>
                            <th>Count</th>
                        </tr></thead>
                        <tbody>`;

                for (let result of resultsData) {
                    tableHtml += `
                        <tr>
                            <td style="${result.sig_better_than_next ? "border-bottom: 1pt dashed black;" : ""}">${result.model}</td>
                            <td>${result.score.toFixed(1)}</td>
                            <td>${result.count}</td>
                        </tr>`;
                }

                tableHtml += `
                        </tbody>
                    </table>`;

                $content.append(tableHtml);

                // Add export links with direct hrefs - no click handlers needed
                // Only show if token is available
                if (token) {
                    const exportLinksHtml = `
                        <div style="margin-top: 10px;">
                            <a href="export-results?campaign_id=${encodeURIComponent(campaign_id)}&token=${encodeURIComponent(token)}&format=pdf" class="abutton">Export PDF</a>
                            <a href="export-results?campaign_id=${encodeURIComponent(campaign_id)}&token=${encodeURIComponent(token)}&format=typst" class="abutton">Export Typst</a>
                            <a href="export-results?campaign_id=${encodeURIComponent(campaign_id)}&token=${encodeURIComponent(token)}&format=latex" class="abutton">Export LaTeX</a>
                        </div>
                    `;
                    $content.append(exportLinksHtml);
                }
            } else {
                $content.html("<p>No ranking data available yet.</p>");
            }
        } catch (error) {
            console.error("Error fetching results:", error);
            $content.html("<p>Error loading ranking data.</p>");
        }


        $content.show();
    });

    // Add event listener for add user button
    if (token !== null && (assignment === "single-stream" || assignment === "dynamic")) {
        el.find(".add-user-btn").on("click", function () {            
            const usersStr = prompt(`How many new users do you want to add to ${campaign_id}?`, "1");
            if (usersStr === null) {
                return;
            }
            const users = parseInt(usersStr);
            if (isNaN(users) || users < 1) {
                notify("Invalid number of users");
                return;
            }
            
            $.ajax({
                url: `add-new-user`,
                method: "POST",
                data: JSON.stringify({ "campaign_id": campaign_id, "token": token, "users": users }),
                contentType: "application/json",
                dataType: "json",
                success: (data) => {
                    notify(`Added ${users} new user(s) ${data.user_id} to campaign ${campaign_id}.`);
                    location.reload();
                },
                error: (XMLHttpRequest) => {
                    const errorMsg = XMLHttpRequest.responseJSON?.error || XMLHttpRequest.responseText || XMLHttpRequest.statusText || "An unknown error occurred";
                    notify("Error adding new user: " + errorMsg);
                },
            });
        });
    }

    // Add event listener for purge/reset campaign button
    if (token !== null) {
        el.find(".purge-campaign-btn").on("click", function () {
            // Create a custom dialog to ask user to choose between purge and reset
            const action = prompt(
                `What would you like to do with campaign ${campaign_id}?\n\n` +
                `Type "purge" to remove the campaign completely (all data will be deleted).\n` +
                `Type "reset" to reset all user accounts (data will be preserved, progress will be reset).`,
                "reset"
            );

            if (action === null) {
                // User cancelled
                return;
            }

            const actionLower = action.toLowerCase().trim();

            if (actionLower === "purge") {
                // Confirm purge action
                if (!confirm(`Are you absolutely sure you want to purge campaign ${campaign_id}?\n\nThis will:\n- Remove the campaign completely\n- Delete all collected data\n- Cannot be undone\n- Campaign will disappear from dashboard`)) {
                    return;
                }

                $.ajax({
                    url: `purge-campaign`,
                    method: "POST",
                    data: JSON.stringify({ "campaign_id": campaign_id, "token": token }),
                    contentType: "application/json",
                    dataType: "json",
                    success: () => {
                        notify(`Campaign ${campaign_id} has been purged.`);
                        // Remove campaign from URL and reload
                        const url = new URL(window.location.href);
                        const params = new URLSearchParams(url.search);
                        const campaignIds = params.getAll("campaign_id");
                        const tokens = params.getAll("token");

                        // Find and remove this campaign
                        const index = campaignIds.indexOf(campaign_id);
                        if (index > -1) {
                            campaignIds.splice(index, 1);
                            tokens.splice(index, 1);
                        }

                        // Rebuild URL
                        url.search = "";
                        campaignIds.forEach((id, i) => {
                            url.searchParams.append("campaign_id", id);
                            if (tokens[i]) {
                                url.searchParams.append("token", tokens[i]);
                            }
                        });

                        window.location.href = url.toString();
                    },
                    error: (XMLHttpRequest) => {
                        const errorMsg = XMLHttpRequest.responseJSON?.error || XMLHttpRequest.responseText || XMLHttpRequest.statusText || "An unknown error occurred";
                        notify("Error purging campaign: " + errorMsg);
                    },
                });
            } else if (actionLower === "reset") {
                // Confirm reset action
                if (!confirm(`Are you sure you want to reset all accounts in campaign ${campaign_id}?\n\nThis will:\n- Reset progress for all users\n- Preserve all collected data\n- Users will annotate new data\n\nThis action cannot be easily undone.`)) {
                    return;
                }

                // Reset all users
                let resetPromises = [];
                for (let user_id in data) {
                    resetPromises.push(
                        $.ajax({
                            url: `reset-campaign`,
                            method: "POST",
                            data: JSON.stringify({ "campaign_id": campaign_id, "user_id": user_id, "token": token }),
                            contentType: "application/json",
                            dataType: "json",
                        })
                    );
                }

                Promise.all(resetPromises)
                    .then(() => {
                        notify(`All accounts in campaign ${campaign_id} have been reset.`);
                        location.reload();
                    })
                    .catch((error) => {
                        const errorMsg = error?.responseJSON?.error || error?.responseText || error?.statusText || "An unknown error occurred";
                        notify("Error resetting accounts: " + errorMsg);
                    });
            } else {
                notify("Invalid choice. Please enter 'purge' or 'reset'.");
            }
        });
    }

    if (token != null) {
        el.find(".reset-campaign").on("click", function () {
            let user_id = $(this).attr("user_id")
            // show dialog to confirm
            if (!confirm(`Are you sure you want to reset progress for user ${$(this).attr("user_id")} in ${campaign_id}?\n\nThe user will annotate new data which will be stored alongside the already-collected data. This action cannot be undone.`)) {
                return
            }
            $.ajax({
                url: `reset-campaign`,
                method: "POST",
                data: JSON.stringify({ "campaign_id": campaign_id, "user_id": user_id, "token": token }),
                contentType: "application/json",
                dataType: "json",
                success: (x) => {
                    notify(`Task for user ${user_id} has been reset.`)
                    location.reload()
                },
                error: (XMLHttpRequest) => {
                    const errorMsg = XMLHttpRequest.responseJSON?.error || XMLHttpRequest.responseText || XMLHttpRequest.statusText || "An unknown error occurred";
                    notify("Error resetting task: " + errorMsg);
                },
            });
        })
        el.find(".edit-note").on("click", function () {
            let user_id = $(this).attr("user_id")
            let current_note = $(this).attr("current_note")
            let prefill = current_note ? current_note : user_id
            let display = current_note ? " / " + current_note : ""
            let new_note = prompt(`Edit name for user ${user_id} ${display}. Empty removes previous name `, prefill)
            if (new_note === null) {
                return;
            }
            $.ajax({
                url: `note-user`,
                method: "POST",
                data: JSON.stringify({ "campaign_id": campaign_id, "user_id": user_id, "token": token, "note": new_note.trim() }),
                contentType: "application/json",
                dataType: "json",
                success: (x) => {
                    notify(`Note for user ${user_id} has been updated.`)
                    location.reload()
                },
                error: (XMLHttpRequest) => {
                    const errorMsg = XMLHttpRequest.responseJSON?.error || XMLHttpRequest.responseText || XMLHttpRequest.statusText || "An unknown error occurred";
                    notify("Error updating note: " + errorMsg);
                },
            });
        })
    }
}

// for each campaign_id, fetch dashboard data and display them in a white-box
(async () => {
    for (let i = 0; i < campaign_ids.length; i++) {
        let campaign_id = campaign_ids[i];
        let token = tokens[i] || null
        try {
            await fetchAndRenderCampaign(campaign_id, token);
        } catch (error: any) {
            const errorMsg = error?.responseJSON?.error || error?.responseText || error?.statusText || "An unknown error occurred";
            notify("Error fetching data: " + errorMsg);
        }
    }
})();


async function handleDownload(url: string, defaultFilename: string) {
    if ('showSaveFilePicker' in window) {
        try {
            const handle = await (window as any).showSaveFilePicker({
                suggestedName: defaultFilename,
                types: [{
                    description: 'JSON Files',
                    accept: { 'application/json': ['.json'] },
                }],
            });
            const response = await fetch(url);
            if (!response.ok || !response.body) {
                throw new Error("Failed to fetch file or body is null.");
            }
            const writable = await handle.createWritable();
            await response.body.pipeTo(writable);
            return;
        } catch (err: any) {
            if (err.name === 'AbortError') {
                return; // User cancelled
            }
            console.error('File System Access API failed, falling back:', err);
        }
    }
    // Fallback if API not supported or failed
    window.location.href = url + `&filename=${encodeURIComponent(defaultFilename)}`;
}

// progress requries an access token
if (tokens.length == 0) {
    $("#download_progress").attr("disabled", "true")
} else {
    const progressUrl = `download-progress?${campaign_ids.map((id, i) => `campaign_id=${encodeURIComponent(id)}&${tokens[i] ? `token=${encodeURIComponent(tokens[i])}` : ''}`).join('&')}`;
    $("#download_progress").attr("href", progressUrl);
    $("#download_progress").on("click", (e) => {
        e.preventDefault();
        handleDownload(progressUrl, "progress.json");
    });
}

const annotationsUrl = `download-annotations?${campaign_ids.map((id, i) => `campaign_id=${encodeURIComponent(id)}&${tokens[i] ? `token=${encodeURIComponent(tokens[i])}` : ''}`).join('&')}`;
$("#download_annotations").attr("href", annotationsUrl);
$("#download_annotations").on("click", (e) => {
    e.preventDefault();
    handleDownload(annotationsUrl, "annotations.json");
});

const campaignsUrl = `download-campaigns?${campaign_ids.map((id, i) => `campaign_id=${encodeURIComponent(id)}&${tokens[i] ? `token=${encodeURIComponent(tokens[i])}` : ''}`).join('&')}`;
$("#download_campaigns").attr("href", campaignsUrl);
$("#download_campaigns").on("click", (e) => {
    e.preventDefault();
    handleDownload(campaignsUrl, "campaigns.json");
});


// add campaign requires main token
if (tokenMain === "") {
    $("#add_campaign").attr("disabled", "true")
}

// Add campaign upload functionality
$("#add_campaign").on("click", function () {
    $("#campaign_file_input").trigger("click");
});

$("#campaign_file_input").on("change", async function (event: JQuery.ChangeEvent) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;

    try {
        const fileContent = await file.text();
        let campaignData;
        try {
            campaignData = JSON.parse(fileContent);
        } catch (e) {
            notify("Error: Invalid JSON file");
            $(this).val('');
            return;
        }

        const response = await $.ajax({
            url: `add-campaign`,
            method: "POST",
            data: JSON.stringify({ campaign_data: campaignData, token_main: tokenMain }),
            contentType: "application/json",
            dataType: "json",
        });

        const url = new URL(window.location.href);
        response.campaigns.forEach((campaign: any) => {
            url.searchParams.append("campaign_id", campaign.campaign_id);
            url.searchParams.append("token", campaign.token);
        });
        window.location.href = url.toString();
    } catch (error) {
        const errorMsg = (error as any)?.responseJSON?.error || "Error adding campaign";
        notify(errorMsg);
    }

    $(this).val('');
});

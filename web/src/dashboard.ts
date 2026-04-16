import './style.css';
import { notify } from "./utils"
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

function delta_to_human(delta: number): string {
    /* Convert a time delta in seconds to a human-readable format */
    if (delta < 60) {
        return `${Math.round(delta)}s`
    } else if (delta < 60 * 60) {
        return `${Math.round(delta / 60)}m`
    } else if (delta < 60 * 60 * 24) {
        return `${Math.round(delta / 60 / 60)}h`
    } else {
        return `${Math.round(delta / 60 / 60 / 24)}d`
    }
}

async function fetchAndRenderCampaign(campaign_id: string, token: string | null) {
    let x = await $.ajax({
        url: `dashboard-data`,
        method: "POST",
        data: JSON.stringify({ "campaign_id": campaign_id, "token": token }),
        contentType: "application/json",
        dataType: "json",
    });
    let data = x.data;
    let assignment = x.assignment;

    let html = ""
    let campaignFinished = 0
    let campaignTotal = 0
    html += `
    <table class="dashboard-table">
        <thead><tr>
            <th style="min-width: 300px;">User ID</th>
            <th style="min-width: 50px;">Progress</th>
            <th style="min-width: 80px;">First</th>
            <th style="min-width: 80px;">Last</th>
            <th style="min-width: 80px;">Time</th>
            <th style="min-width: 70px;">Checks</th>
            <th style="min-width: 50px;">Actions</th>
        </tr></thead>
        <tbody>`
    for (let user_id in data) {
        const progress = data[user_id]["progress"] as Array<string | object>
        const progress_total = progress.length

        // Calculate regular progress - count "completed" items
        let progress_count = progress.filter(v => v === "completed").length
        if (assignment == "dynamic") {
            progress_count = progress.map(l => Object.values(l).filter(v => v === "completed").length).reduce((a, b) => a + b, 0)
        }

        // Calculate welcome progress separately
        let welcome_count = 0
        let welcome_total = 0
        let progress_display = ''

        if (data[user_id]["progress_welcome"]) {
            const welcome_progress = data[user_id]["progress_welcome"] as Array<boolean>
            welcome_count = welcome_progress.reduce((a, b) => a + (b ? 1 : 0), 0)
            welcome_total = welcome_progress.length
        }

        // For single-stream and dynamic, show: finished_by_user
        // For task-based, show finished_by_user/total
        if (assignment === "single-stream" || assignment === "dynamic") {
            if (welcome_total > 0) {
                // Show as "welcome_done/welcome_total+finished"
                progress_display = `${welcome_count}/${welcome_total}+${progress_count}`
            } else {
                // No welcome items, show as "finished"
                progress_display = `${progress_count}`
            }
        } else {
            // Task-based: use traditional format
            if (welcome_total > 0) {
                // Show as "welcome_done/welcome_total+regular_done/regular_total"
                progress_display = `${welcome_count}/${welcome_total}+${progress_count}/${progress_total}`
            } else {
                // No welcome items, just show regular progress
                progress_display = `${progress_count}/${progress_total}`
            }
        }

        // Shared streams mark others' work as "completed_foreign"; backend treats that as done
        // for threshold_passed, but counting only "completed" never reaches total_total.
        let progress_slots_filled = progress_count
        if (assignment === "single-stream") {
            progress_slots_filled = progress.filter(
                (v) => v === "completed" || v === "completed_foreign"
            ).length
        } else if (assignment === "dynamic") {
            progress_slots_filled = progress
                .map((l) =>
                    Object.values(l as object).filter(
                        (v) => v === "completed" || v === "completed_foreign"
                    ).length
                )
                .reduce((a, b) => a + b, 0)
        }

        // Calculate total for status determination
        let total_count = welcome_count + progress_slots_filled
        let total_total = welcome_total + progress_total
        campaignFinished += total_count
        campaignTotal += total_total

        let threshold_passed = data[user_id]["threshold_passed"]
        let status = ''
        if (data[user_id]["time"] == 0)
            status = '💤'
        else if (data[user_id]["time"] != 0 && total_count == total_total) {
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
        html += `<td>${status} ${user_id}</td>`

        // time section - show separate progress
        html += `<td>${progress_display}</td>`
        if (data[user_id]["time_start"] == null) {
            html += `<td title="N/A"></td>`
        } else {
            html += `<td title="${new Date(data[user_id]["time_start"] * 1000).toLocaleString()}">${delta_to_human(Date.now() / 1000 - data[user_id]["time_start"])} ago</td>`
        }
        if (data[user_id]["time_end"] == null) {
            html += `<td title="N/A"></td>`
        } else {
            html += `<td title="${new Date(data[user_id]["time_end"] * 1000).toLocaleString()}">${delta_to_human(Date.now() / 1000 - data[user_id]["time_end"])} ago</td>`
        }
        html += `<td>${Math.round(data[user_id]["time"] / 60)}m</td>`

        let validation_passed = data[user_id]["validations"].reduce((a: number, b: boolean) => a + (b ? 1 : 0), 0)
        let validation_total = data[user_id]["validations"].length
        html += `<td><span style="${validation_passed != validation_total ? 'color: #c75050;' : ''}">${validation_passed}</span><span style="color: #333;">/${validation_total}</span></td>`

        // actions section
        html += `<td>
            <a href="${data[user_id]["url"]}">🔗</a>
            &nbsp;&nbsp;
            <a href="${data[user_id]["url"]}&frozen" title="View only (frozen)">👁️</a>`

        // Hide delete button for dynamic assignments - deletion not supported due to shared data pool
        if (assignment !== "dynamic") {
            html += `
            &nbsp;&nbsp;
            <span class="reset-task" user_id="${user_id}" ${token == null ? "disabled" : ""}>🗑️</span>`
        }

        html += `</td>`
        html += '</tr>'
    }
    html += '</tbody></table>'

    let pctTitle = ""
    if (campaignTotal > 0) {
        const pct = (campaignFinished / campaignTotal) * 100
        pctTitle = ` — ${(Math.round(pct * 10) / 10).toFixed(1)}%`
    }

    // link to campaign-specific dashboard
    let dashboard_url = `${window.location.origin}/dashboard.html?campaign_id=${encodeURIComponent(campaign_id)}${token != null ? `&token=${encodeURIComponent(token)}` : ''}`

    // Create buttons HTML for the header (only if token is available)
    let buttonsHtml = '';
    if (token !== null && token !== undefined) {
        buttonsHtml = `
            <div style="display: inline-block; vertical-align: top; gap: 10px; width: 150px;">
                
            </div>
        `;
    }

    let el = $(`
        <div class="white-box">
            <div style="">
                <h3 style="margin: 0;">
                ${campaign_id}${pctTitle}
                <a href="${dashboard_url}">🔗</a>
                <a class="show-ranking-btn">⚖️</a>
                ${token !== null ? '<a class="purge-campaign-btn" style="cursor: pointer;">🗑️</a>' : ''}
                </h3>
            </div>
            <div class="dashboard-content">
                ${html}
            </div><div class="ranking-content" style="display: none; margin-top: -30px;">
            </div>
        </div>
        <br>
        `)

    $("#dashboard_div").append(el)

    // Add event listener for show/hide ranking button
    el.find(".show-ranking-btn").on("click", async function () {
        const $content = el.find(".ranking-content");

        $(this).remove()

        // Check if data is already loaded
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
                            <th>Model</th>
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
                            <a href="/export-results?campaign_id=${encodeURIComponent(campaign_id)}&token=${encodeURIComponent(token)}&format=pdf" class="abutton">Export PDF</a>
                            <a href="/export-results?campaign_id=${encodeURIComponent(campaign_id)}&token=${encodeURIComponent(token)}&format=typst" class="abutton">Export Typst</a>
                            <a href="/export-results?campaign_id=${encodeURIComponent(campaign_id)}&token=${encodeURIComponent(token)}&format=latex" class="abutton">Export LaTeX</a>
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
                            url: `reset-task`,
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
        el.find(".reset-task").on("click", function () {
            let user_id = $(this).attr("user_id")
            // show dialog to confirm
            if (!confirm(`Are you sure you want to reset progress for user ${$(this).attr("user_id")} in ${campaign_id}?\n\nThe user will annotate new data which will be stored alongside the already-collected data. This action cannot be undone.`)) {
                return
            }
            $.ajax({
                url: `reset-task`,
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


// progress requries an access token
if (tokens.length == 0) {
    $("#download_progress").attr("disabled", "true")
} else {
    $("#download_progress").attr("href", `/download-progress?${campaign_ids.map((id, i) => `campaign_id=${encodeURIComponent(id)}&${tokens[i] ? `token=${encodeURIComponent(tokens[i])}` : ''}`).join('&')}`)
}
$("#download_annotations").attr("href", `/download-annotations?${campaign_ids.map((id, i) => `campaign_id=${encodeURIComponent(id)}&${tokens[i] ? `token=${encodeURIComponent(tokens[i])}` : ''}`).join('&')}`)

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
        url.searchParams.append("campaign_id", response.campaign_id);
        url.searchParams.append("token", response.token);
        window.location.href = url.toString();
    } catch (error) {
        const errorMsg = (error as any)?.responseJSON?.error || "Error adding campaign";
        notify(errorMsg);
    }

    $(this).val('');
});

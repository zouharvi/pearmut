import './style.css';
import $ from 'jquery';

import { get_next_item, get_i_item, log_response } from './connector';
import {
    notify,
    ErrorSpan,
    CharData,
    redrawProgress,
    createSpanToolbox,
    updateToolboxPosition,
    Validation,
    validateResponse,
    DataGoodbye,
    DataForm,
    DataFormItem,
    ProtocolInfo,
    SliderConfig,
    isMediaContent,
    contentToCharSpans,
    isSpanComplete,
    computeWordBoundaries,
    detectTextDirection,
    debounce,
    getErrorSpansForModel,
    DocumentResponse,
    DataPayload,
    DataPayloadItem,
    MQM_ERROR_CATEGORIES,
    MQM_SEVERITIES,
} from './utils';

// Check if frozen mode is enabled (view-only, no annotations)
const searchParams = new URLSearchParams(window.location.search)
const frozenMode = searchParams.has("frozen")
const debugMode = searchParams.has("debug")

const state = {
    response_log: [] as Array<DocumentResponse>,
    action_log: [] as Array<any>,
    validations: [] as Array<Record<string, Validation> | undefined>,
    payload_items: [] as Array<DataPayloadItem>,  // Store current payload items to check skippable
    output_blocks: [] as Array<JQuery<HTMLElement>>,
    settings: {
        show_alignment: true,
        word_level: false,
    },
    has_unsaved_work: false,
    skip_mode: false,
    // Protocol settings for check_unlock
    protocol: "",
    protocol_error_spans: false,
    protocol_error_categories: false,
    mqm_categories: MQM_ERROR_CATEGORIES,
    mqm_severities: MQM_SEVERITIES as string[],
}

// Prevent accidental refresh/navigation when there is ongoing work
window.addEventListener('beforeunload', (event) => {
    if (state.has_unsaved_work) {
        event.preventDefault()
    }
})

$("#toggle_differences").on("change", function () {
    if ($(this).is(":checked")) {
        $(".difference").removeClass("hidden")
    } else {
        $(".difference").addClass("hidden")
    }
})

function check_unlock() {
    // In frozen mode, always keep the button disabled
    if (frozenMode) {
        $("#button_next").attr("disabled", "disabled")
        $("#button_next").val("Next 🔒")
        $("#button_skip").hide()
        return
    }

    // Check if all error spans are complete (have required severity and category based on protocol)
    if (state.protocol_error_spans || state.protocol_error_categories) {
        for (const doc_responses of state.response_log) {
            for (const r of Object.values(doc_responses)) {
                for (const span of r.error_spans) {
                    if (!isSpanComplete(span, state.protocol_error_categories)) {
                        $("#button_next").attr("disabled", "disabled")
                        $("#button_next").val("Incomplete 🚧")
                        return
                    }
                }
            }
        }
    }


    let incomplete_items_i = Array<number>()

    // Check if all scores are set
    state.response_log.forEach((doc_responses, i) =>
        Object.values(doc_responses).forEach(r => {
            if (r.sliders) {
                // Custom sliders mode: all sliders must be non-null (no score required)
                // Note: when sliders is {} (empty, from sliders: []), Object.values returns []
                // and every() returns true (vacuous truth), allowing immediate progression
                if (!Object.values(r.sliders).every(val => val !== null)) {
                    incomplete_items_i.push(i)
                }
            } else {
                // Single score mode: the score must be set
                if (r.score == null) {
                    incomplete_items_i.push(i)
                }
            }
        })
    )
    if (incomplete_items_i.length > 0) {
        $("#button_next").attr("disabled", "disabled")
        $("#button_next").val("Incomplete 🚧")
        // Check if all incomplete items are skippable
        if (debugMode || incomplete_items_i.every(item_i => state.payload_items[item_i].skippable)) {
            $("#button_skip").show()
        } else {
            $("#button_skip").hide()
        }
        return
    }

    // All items complete - enable Next button and hide Skip button
    $("#button_next").removeAttr("disabled")
    $("#button_next").val("Next ✅")
    $("#button_skip").hide()
}

/**
 * Cleanup function to remove toolboxes and handlers from previous item
 * Must be called before loading a new item to prevent memory leaks and stale UI
 */
function cleanupPreviousItem(): void {
    // Remove all toolboxes appended to body
    $(".span_toolbox_parent").remove()
    // Remove resize handlers for toolbox positioning (use namespace to avoid removing other handlers)
    $(window).off('resize.toolbox')
}

function _textfield_button_html(item_i: number, model: string, mode: string | null | undefined): string {
    if (!mode) return ""  // null or undefined - don't show textfield

    if (mode === "hidden") {
        return `
        <button class="textfield_toggle" id="textfield_toggle_${item_i}_${model}">✏️</button>
        `
    }

    return ""
}


function _textfield_html(item_i: number, model: string, mode: string | null | undefined): string {
    if (!mode) return ""  // null or undefined - don't show textfield

    if (mode === "hidden") {
        return `
        <textarea class="output_textfield" id="textfield_${item_i}_${model}" style="display: none;" placeholder="Type here..."></textarea>
        `
    } else if (mode === "visible" || mode === "prefilled") {
        return `
        <textarea class="output_textfield" id="textfield_${item_i}_${model}" placeholder="Type here..."></textarea>
        `
    }

    return ""
}

function _slider_html(item_i: number, model: string, sliders?: SliderConfig[]): string {
    // If sliders is explicitly an empty array, show no sliders
    if (sliders && sliders.length === 0) {
        return '<div class="output_response"></div>'
    }

    // If no custom sliders specified (undefined), use default single slider
    if (!sliders) {
        if (state.protocol == "cESA") {
            return `
        <div class="output_response">
          <div style="width: calc(100% - 30px);">
            <input type="range" min="0" max="100" value="-1" step="5" id="response_${item_i}_${model}">
          </div>
        </div>
        <div class="slider_label slider_label_cESA">❓/100</div>
        `
        } else {
            return `
        <div class="output_response">
          <div style="width: 100%;">
            <input type="range" min="0" max="100" value="-1" step="1" id="response_${item_i}_${model}">
            <div class="slider_anchor_parent">
                <span class="slider_anchor_simple">▼</span>
                <span class="slider_anchor_simple">▼</span>
            </div>
          </div>
          <span class="slider_label">❓/100</span>
        </div>
        `
        }
    }

    // Generate multiple sliders with labels (no Score slider when custom sliders are defined)
    let html = '<div class="output_response">'

    // Add custom sliders
    for (const slider of sliders) {
        html += `
          <div class="slider_container">
            <label class="slider_name">${slider.name}</label>
            <input type="range" min="${slider.min}" max="${slider.max}" step="${slider.step}" value="${slider.min - 1}" id="response_${item_i}_${model}_${slider.name}" data-slider="${slider.name}">
            <span class="slider_label" data-slider="${slider.name}">❓/${slider.max}</span>
          </div>
        `
    }

    html += '</div>'
    return html
}

function createOutputBlock(item: DataPayloadItem, item_i: number, info: ProtocolInfo): JQuery<HTMLElement> {
    // character-level stuff won't work on media tags
    let no_src_char = !item.src || isMediaContent(item.src)
    let no_ref_char = !item.ref || isMediaContent(item.ref)

    // Detect text direction for source and reference
    let src_dir = item.src && !no_src_char ? detectTextDirection(item.src) : 'ltr'
    let ref_dir = item.ref && !no_ref_char ? detectTextDirection(item.ref) : 'ltr'

    // Build character spans for source and reference
    let src_chars = ""
    if (item.src) {
        src_chars = no_src_char ? item.src : contentToCharSpans(item.src, "src_char")
    }
    let ref_chars = ""
    if (item.ref) {
        ref_chars = no_ref_char ? item.ref : contentToCharSpans(item.ref, "ref_char")
    }

    // Build source and reference boxes - only if they exist
    let srcRefBoxes = ""
    if (item.src) {
        let src_style = src_dir === 'rtl' ? ' style="direction: rtl;"' : ''
        srcRefBoxes += `<div class="output_src"${src_style}>${src_chars}</div>`
    }
    if (item.ref) {
        let ref_style = ref_dir === 'rtl' ? ' style="direction: rtl;"' : ''
        srcRefBoxes += `<div class="output_ref"${ref_style}>${ref_chars}</div>`
    }

    let output_block = $(`
    <div class="output_block">
      <span class="instructions_message"></span>
      <div class="output_item">
        ${srcRefBoxes}
        <div class="output_scrollable"></div>
      </div>
    </div>
    `)

    if (item.instructions) {
        output_block.find(".instructions_message").html(item.instructions)
    }

    // Add each model's output
    for (const [model, tgt] of Object.entries(item.tgt)) {
        let no_tgt_char = isMediaContent(tgt)
        let tgt_dir = !no_tgt_char ? detectTextDirection(tgt) : 'ltr'
        let tgt_chars = no_tgt_char ? tgt : (contentToCharSpans(tgt, "tgt_char") + (state.protocol_error_spans ? ' <span class="tgt_char char_missing">[missing]</span>' : ""))
        let tgt_style = tgt_dir === 'rtl' ? ' style="direction: rtl;"' : ''

        let candidate_block = $(`
        <div class="output_candidate" data-candidate="${model}" data-model="${model}">
          <div class="output_tgt"${tgt_style}>${tgt_chars}</div>
          ${_slider_html(item_i, model, info.sliders)}
        </div>
        `)

        // Add model name at the top of the candidate block if enabled
        if (info.show_model_names) {
            let model_name_div = $('<div class="model_name"></div>').text(model)
            candidate_block.prepend(model_name_div)
        }

        candidate_block.find(".output_response").prepend(_textfield_button_html(item_i, model, info.textfield))
        candidate_block.append(_textfield_html(item_i, model, info.textfield))

        output_block.find(".output_scrollable").append(candidate_block)
    }

    // make the weight of the scrollable be number of items
    output_block.find(".output_scrollable").css("flex", `${Object.keys(item.tgt).length}`)

    return output_block
}

function setupCandidateInteractions(
    candidate_block: JQuery<HTMLElement>,
    item_i: number,
    model: string,
    tgt: string,
    response: DataPayload,
    src_chars_els: HTMLElement[],
    ref_chars_els: HTMLElement[],
    output_block: JQuery<HTMLElement>
) {
    let no_tgt_char = isMediaContent(tgt)
    let item = response.payload[item_i]

    // Setup character-level interactions for this model's output
    // Compute word boundaries for the target text
    let _tgt_chars_els = candidate_block.find(".tgt_char").toArray()
    let tgt_word_boundaries = no_tgt_char ? [] : computeWordBoundaries(_tgt_chars_els.map(el => $(el).text()))
    let tgt_chars_objs: Array<CharData> = no_tgt_char ? [] : _tgt_chars_els.map((el, idx) => ({
        "el": $(el),
        "toolbox": null,
        "error_span": null,
        "word_start": idx < tgt_word_boundaries.length ? tgt_word_boundaries[idx][0] : idx,
        "word_end": idx < tgt_word_boundaries.length ? tgt_word_boundaries[idx][1] : idx,
    }))
    let state_i: null | number = null
    let missing_i = state.protocol_error_spans ? tgt_chars_objs.findIndex(obj => obj.el.hasClass("char_missing")) : -1

    if (!no_tgt_char) {
        tgt_chars_objs.forEach((obj, i) => {
            let is_missing = (i == missing_i)

            // leaving target character
            $(obj.el).on("mouseleave", function () {
                $(".src_char").removeClass("highlighted")
                $(".ref_char").removeClass("highlighted")
                $(".tgt_char").removeClass("highlighted")
                $(".tgt_char").removeClass("highlighted_active")

                // hide corresponding toolbox after delay if error severity is set
                if (obj.error_span != null && obj.error_span.severity != null && (!state.protocol_error_categories || (obj.error_span.category != null && obj.error_span.category?.includes("/")))) {
                    const toolbox = obj.toolbox;
                    if (toolbox) {
                        const timeoutId = window.setTimeout(() => {
                            toolbox.css("display", "none")
                        }, 500);
                        toolbox.data("hide-timeout", timeoutId);
                    }
                }
            })

            // entering target character
            $(obj.el).on("mouseenter", function () {
                $(".src_char").removeClass("highlighted")
                $(".ref_char").removeClass("highlighted")
                $(".tgt_char").removeClass("highlighted")
                if (state.settings.show_alignment && !is_missing) {
                    // Highlight corresponding characters in source
                    if (src_chars_els.length > 0) {
                        let src_i = Math.round(i / tgt_chars_objs.length * src_chars_els.length)
                        for (let j = Math.max(0, src_i - 5); j <= Math.min(src_chars_els.length - 1, src_i + 5); j++) {
                            $(src_chars_els[j]).addClass("highlighted")
                        }
                    }
                    // Highlight corresponding characters in reference
                    if (ref_chars_els.length > 0) {
                        let ref_i = Math.round(i / tgt_chars_objs.length * ref_chars_els.length)
                        for (let j = Math.max(0, ref_i - 5); j <= Math.min(ref_chars_els.length - 1, ref_i + 5); j++) {
                            $(ref_chars_els[j]).addClass("highlighted")
                        }
                    }
                    // Highlight corresponding characters in all other candidates
                    let relative_pos = i / tgt_chars_objs.length
                    // if not our candidate
                    output_block.find(".output_candidate").each(function () {
                        if ($(this).attr("data-candidate")! == model) {
                            return
                        }
                        let other_tgt_chars = $(this).find(".tgt_char")
                        let other_i = Math.round(relative_pos * other_tgt_chars.length)
                        for (let j = Math.max(0, other_i - 5); j <= Math.min(other_tgt_chars.length - 1, other_i + 5); j++) {
                            other_tgt_chars.eq(j).addClass("highlighted")
                        }
                    })
                }
                if (state_i != null && !is_missing) {
                    // In word-level mode, expand selection preview to word boundaries
                    let preview_left = Math.min(state_i, i)
                    let preview_right = Math.max(state_i, i)
                    if (state.settings.word_level && state_i != missing_i) {
                        preview_left = tgt_chars_objs[preview_left].word_start
                        preview_right = tgt_chars_objs[preview_right].word_end
                    }
                    for (let j = preview_left; j <= preview_right; j++) {
                        $(tgt_chars_objs[j].el).addClass("highlighted")
                    }
                } else if (state.settings.word_level && !is_missing && state_i == null) {
                    // Highlight current word on hover when in word-level mode (no active selection)
                    for (let j = obj.word_start; j <= obj.word_end; j++) {
                        $(tgt_chars_objs[j].el).addClass("highlighted")
                    }
                }

                // check if inside a span
                if (tgt_chars_objs[i].error_span != null) {
                    let span = tgt_chars_objs[i].error_span!
                    // highlight the whole span if we're in one
                    for (let j = span.start_i; j <= span.end_i; j++) {
                        $(tgt_chars_objs[j].el).addClass("highlighted_active")
                    }

                    const toolbox = tgt_chars_objs[span.start_i].toolbox;
                    if (toolbox) {
                        const timeoutId = toolbox.data("hide-timeout");
                        if (timeoutId) {
                            window.clearTimeout(timeoutId);
                            toolbox.removeData("hide-timeout");
                        }
                        toolbox.css("display", "block")
                    }
                }
            })

            // add spans and toolbox only in case the protocol asks for it
            if (state.protocol_error_spans || state.protocol_error_categories) {
                $(obj.el).on("click", function () {
                    // In frozen mode, do not allow creating new error spans
                    if (frozenMode) return

                    if (is_missing) {
                        state_i = missing_i
                    }
                    if (state_i != null) {
                        // check if we're not overlapping
                        let left_i = Math.min(state_i, i)
                        let right_i = Math.max(state_i, i)

                        // Expand to word boundaries if word-level mode is enabled
                        if (state.settings.word_level && !is_missing && state_i != missing_i) {
                            left_i = tgt_chars_objs[left_i].word_start
                            right_i = tgt_chars_objs[right_i].word_end
                        }

                        state_i = null
                        $(".src_char").removeClass("highlighted")
                        candidate_block.find(".tgt_char").removeClass("highlighted")

                        let error_span: ErrorSpan = {
                            "start_i": left_i,
                            "end_i": right_i,
                            "category": null,
                            "severity": null,
                        }

                        if (state.response_log[item_i][model].error_spans.some(span => {
                            return (
                                (left_i <= span.start_i && right_i >= span.start_i) ||
                                (left_i <= span.end_i && right_i >= span.end_i)
                            )
                        })) {
                            notify("Cannot create overlapping error spans")
                            return
                        }

                        // create toolbox
                        let toolbox = createSpanToolbox(
                            state.protocol_error_categories,
                            error_span,
                            tgt_chars_objs,
                            left_i,
                            right_i,
                            () => {
                                // onDelete callback
                                state.response_log[item_i][model].error_spans = state.response_log[item_i][model].error_spans.filter(span => span != error_span)
                                state.action_log.push({ "time": Date.now() / 1000, "action": "delete_span", "index": item_i, "model": model, "start_i": left_i, "end_i": right_i })
                                state.has_unsaved_work = true
                                check_unlock()
                            },
                            () => {
                                check_unlock()
                            },
                            frozenMode,
                            state.mqm_categories,
                            state.mqm_severities
                        )

                        $("body").append(toolbox)

                        // handle hover on toolbox
                        toolbox.on("mouseenter focusin contextmenu", function (e) {
                            if (e.type === "contextmenu") e.preventDefault();
                            const timeoutId = toolbox.data("hide-timeout");
                            if (timeoutId) {
                                window.clearTimeout(timeoutId);
                                toolbox.removeData("hide-timeout");
                            }
                            toolbox.css("display", "block")
                            check_unlock()
                        })
                        // handle hover on toolbox
                        toolbox.on("mouseleave focusout", function () {
                            // hide if severity is set for ESA or both severity and category are set for MQM
                            if (error_span.severity != null && (!state.protocol_error_categories || (error_span.category != null && error_span.category?.includes("/")))) {
                                const timeoutId = window.setTimeout(() => {
                                    toolbox.css("display", "none")
                                    check_unlock()
                                }, 500);
                                toolbox.data("hide-timeout", timeoutId);
                            }
                        })

                        // set up callback to reposition toolbox on resize         
                        $(window).on('resize.toolbox', () => updateToolboxPosition(toolbox, $(tgt_chars_objs[left_i].el)))
                        updateToolboxPosition(toolbox, $(tgt_chars_objs[left_i].el))

                        // store error span
                        state.response_log[item_i][model].error_spans.push(error_span)
                        state.action_log.push({ "time": Date.now() / 1000, "action": "create_span", "index": item_i, "model": model, "start_i": left_i, "end_i": right_i })
                        state.has_unsaved_work = true
                        for (let j = left_i; j <= right_i; j++) {
                            $(tgt_chars_objs[j].el).addClass("error_unknown")
                            tgt_chars_objs[j].toolbox = toolbox
                            tgt_chars_objs[j].error_span = error_span
                        }

                        check_unlock()
                    } else {
                        // check if we are in existing span
                        if (state.response_log[item_i][model].error_spans.some(span => i >= span.start_i && i <= span.end_i)) {
                            notify("Cannot create overlapping error spans")
                            $(".src_char").removeClass("highlighted")
                            candidate_block.find(".tgt_char").removeClass("highlighted")
                            return
                        }

                        state_i = i
                    }
                })
            }
        })
    }

    // Load error spans - use payload_existing if available, otherwise use item.error_spans
    const existingErrorSpans = response.payload_existing?.annotation[item_i]?.[model]?.error_spans
    const candidateSpans = existingErrorSpans || getErrorSpansForModel(item.error_spans, model)

    if (!no_tgt_char && (state.protocol_error_spans || state.protocol_error_categories) && candidateSpans.length > 0) {
        // Only reset if loading from payload_existing (to avoid duplicating pre-filled spans)
        if (existingErrorSpans) {
            state.response_log[item_i][model].error_spans = []
        }

        for (const prefilled of candidateSpans) {
            const left_i = prefilled.start_i, right_i = prefilled.end_i
            if (left_i < 0 || right_i >= tgt_chars_objs.length || left_i > right_i) continue
            let error_span: ErrorSpan = { ...prefilled }
            state.response_log[item_i][model].error_spans.push(error_span)

            let toolbox = createSpanToolbox(
                state.protocol_error_categories, error_span, tgt_chars_objs, left_i, right_i, () => {
                    state.response_log[item_i][model].error_spans = state.response_log[item_i][model].error_spans.filter(s => s != error_span)
                    state.action_log.push({ "time": Date.now() / 1000, "action": "delete_span", "index": item_i, "model": model, "start_i": left_i, "end_i": right_i })
                    state.has_unsaved_work = true
                }, () => {
                    check_unlock()
                },
                frozenMode,
                state.mqm_categories,
                state.mqm_severities
            )
            $("body").append(toolbox)
            toolbox.on("mouseenter", () => {
                const timeoutId = toolbox.data("hide-timeout");
                if (timeoutId) {
                    window.clearTimeout(timeoutId);
                    toolbox.removeData("hide-timeout");
                }
                toolbox.css("display", "block");
                check_unlock()
            })
            toolbox.on("mouseleave", () => {
                if (error_span.severity != null && (!state.protocol_error_categories || (error_span.category != null && error_span.category?.includes("/")))) {
                    const timeoutId = window.setTimeout(() => {
                        toolbox.css("display", "none");
                        check_unlock()
                    }, 500);
                    toolbox.data("hide-timeout", timeoutId);
                }
            })
            $(window).on('resize.toolbox', () => updateToolboxPosition(toolbox, $(tgt_chars_objs[left_i].el)))

            for (let j = left_i; j <= right_i; j++) {
                $(tgt_chars_objs[j].el).addClass(error_span.severity ? `error_${error_span.severity}` : "error_unknown")
                tgt_chars_objs[j].toolbox = toolbox
                tgt_chars_objs[j].error_span = error_span
            }
            if (error_span.severity != null && (!state.protocol_error_categories || (error_span.category != null && error_span.category?.includes("/")))) {
                toolbox.css("display", "none")
            }
        }
    }

    // Setup slider(s) for this model
    const hasCustomSliders = response.info.sliders && response.info.sliders.length > 0
    const hasNoSliders = response.info.sliders !== undefined && response.info.sliders.length === 0

    if (hasCustomSliders) {
        // Multiple sliders mode (no Score slider when custom sliders are defined)
        const allSliders = response.info.sliders!

        for (const sliderConfig of allSliders) {
            const sliderName = sliderConfig.name
            const sliderMax = sliderConfig.max
            let slider = candidate_block.find(`input[data-slider="${CSS.escape(sliderName)}"]`)
            let label = candidate_block.find(`.slider_label[data-slider="${CSS.escape(sliderName)}"]`)

            slider.on("click input", function () {
                // In frozen mode, do not allow changing scores
                if (frozenMode) return

                let val = parseInt((<HTMLInputElement>this).value)
                label.text(`${val}/${sliderMax}`)

                // Store in sliders field
                if (state.response_log[item_i][model].sliders![sliderName] == null) {
                    state.response_log[item_i][model].sliders![sliderName] = val
                    state.has_unsaved_work = true
                    check_unlock()
                    state.action_log.push({ "time": Date.now() / 1000, "action": sliderName, "index": item_i, "model": model, "value": val })
                }
            })

            slider.on("change", function () {
                // In frozen mode, do not allow changing scores
                if (frozenMode) return

                let val = parseInt((<HTMLInputElement>this).value)
                label.text(`${val}/${sliderMax}`)

                // Store in sliders field
                state.response_log[item_i][model].sliders![sliderName] = val
                state.action_log.push({ "time": Date.now() / 1000, "action": sliderName, "index": item_i, "model": model, "value": val })
                state.has_unsaved_work = true
                check_unlock()
            })

            // Disable slider in frozen mode
            if (frozenMode) {
                slider.prop("disabled", true)
            }

            // Pre-fill score from payload_existing if available
            let existingScore: number | null = null
            existingScore = response.payload_existing?.annotation[item_i]?.[model]?.sliders?.[sliderName] ?? null

            if (existingScore != null) {
                slider.val(existingScore)
                label.text(`${existingScore}/${sliderMax}`)
                state.response_log[item_i][model].sliders![sliderName] = existingScore
            }
        }
    } else if (!hasNoSliders) {
        // Single slider mode (default Score slider)
        let slider = candidate_block.find("input[type='range']")
        let label = candidate_block.find(".slider_label")

        function updateSliderVisual(val: number) {
            label.text(`${val}/100`)
            if (response.info.protocol == "cESA") {
                let text = `${val >= 85 ? "very good" : val >= 65 ? "good" : val >= 45 ? "acceptable" : val >= 25 ? "borderline" : "not&nbsp;acceptable"}`
                label.html(`(${text})&nbsp;&nbsp;${val}/100`)
            }

            if (!response.info.slider_colors) return
            slider.parents(".output_response").css("background-color", `color-mix(in lab, color-mix(in lab, red ${100 - val}%, green ${val}%), white 30%)`)
        }


        slider.on("click input", function (event) {
            // In frozen mode, do not allow changing scores
            if (frozenMode) return

            let val = parseInt((<HTMLInputElement>this).value)
            state.response_log[item_i][model].score = val
            updateSliderVisual(val)

            if (state.response_log[item_i][model].score == null) {
                state.has_unsaved_work = true
                check_unlock()
                state.action_log.push({ "time": Date.now() / 1000, "action": "score", "index": item_i, "model": model, "value": val })
            }
        })
        slider.on("change", function () {
            // In frozen mode, do not allow changing scores
            if (frozenMode) return
            let val = parseInt((<HTMLInputElement>this).value)
            if (response.info.protocol === "ESA" && val < 80 && state.response_log[item_i][model].error_spans.length === 0) {
                // Warn if ESA protocol, score < 80, and no error spans marked
                notify("⚠️ Warning: score is below 80 but no error spans have been marked.")
            } else if (response.info.protocol === "cESA" && val < 85 && state.response_log[item_i][model].error_spans.length === 0) {
                // Warn if cESA protocol, score < 85, and no error spans marked
                notify("⛔ Error: score is below 85 but no error spans have been marked.<br>⛔ Please highlight errors in the translation.")
            }

            state.response_log[item_i][model].score = val
            state.has_unsaved_work = true
            updateSliderVisual(val)
            check_unlock()
            // push only for change which happens just once
            state.action_log.push({ "time": Date.now() / 1000, "action": "score", "index": item_i, "model": model, "value": val })
        })

        // Disable slider in frozen mode
        if (frozenMode) {
            slider.prop("disabled", true)
        }

        // Pre-fill score from payload_existing if available
        const existingScore = response.payload_existing?.annotation[item_i]?.[model]?.score
        if (existingScore != null) {
            slider.val(existingScore)
            updateSliderVisual(existingScore)
            state.response_log[item_i][model].score = existingScore
        }
    }

    // Setup textfield if enabled
    if (response.info.textfield) {
        const textfield = candidate_block.find(`#textfield_${item_i}_${CSS.escape(model)}`)
        const toggle = candidate_block.find(`#textfield_toggle_${item_i}_${CSS.escape(model)}`)

        // Pre-fill with model output if mode is "prefilled"
        // Note: tgt is from trusted campaign data, jQuery .val() safely escapes any content
        if (response.info.textfield === "prefilled") {
            textfield.val(tgt)
            state.response_log[item_i][model].textfield = tgt
        }

        // Handle toggle button for "hidden" mode
        if (response.info.textfield === "hidden") {
            toggle.on("click", function () {
                if (textfield.is(":visible")) {
                    textfield.hide()
                } else {
                    textfield.show()
                }
            })
        }

        // Handle textfield input with debouncing to reduce log volume
        const logTextfieldInput = debounce(() => {
            const val = textfield.val() as string
            state.action_log.push({ "time": Date.now() / 1000, "action": "textfield", "index": item_i, "model": model, "value": val })
        }, 500)

        textfield.on("input", function () {
            // In frozen mode, do not allow changing textfield
            if (frozenMode) return

            let val = (<HTMLTextAreaElement>this).value
            state.response_log[item_i][model].textfield = val
            state.has_unsaved_work = true
            // Log with debounce to avoid excessive logging during typing
            logTextfieldInput()
        })

        // Disable textfield in frozen mode
        if (frozenMode) {
            textfield.prop("disabled", true)
        }

        // Pre-fill textfield from payload_existing if available (overrides prefilled mode)
        const existingTextfield = response.payload_existing?.annotation[item_i]?.[model]?.textfield
        if (existingTextfield != null) {
            textfield.val(existingTextfield)
            state.response_log[item_i][model].textfield = existingTextfield
        }
    }
}

async function display_next_payload(response: DataPayload) {
    // Cleanup toolboxes and handlers from previous item
    cleanupPreviousItem()

    redrawProgress(response.info.item_i, response.progress_welcome, response.progress, navigate_to_item)
    $("#progress").toggle(response.info.show_progress !== false)
    $("#time").text(`Time: ${Math.round(response.time / 60)}m`)

    let data = response.payload
    // Initialize response log - use payload_existing if available
    if (response.payload_existing) {
        state.response_log = response.payload_existing.annotation.map(docResponses => {
            const result: DocumentResponse = {}
            for (const [model, r] of Object.entries(docResponses)) {
                result[model] = {
                    "score": r.score,
                    "sliders": r.sliders ? { ...r.sliders } : undefined,
                    "error_spans": r.error_spans ? [...r.error_spans] : [],
                    "textfield": r.textfield ?? null,
                }
            }
            return result
        })
        // Reload comment if it exists
        if (response.payload_existing.comment) {
            $("#settings_comment").val(response.payload_existing.comment)
        } else {
            $("#settings_comment").val("")
        }
    } else {
        state.response_log = data.map(item => {
            const result: DocumentResponse = {}
            for (const model of Object.keys(item.tgt)) {
                // Check if custom sliders are defined (including empty array)
                const hasCustomSliders = response.info.sliders !== undefined
                result[model] = {
                    "score": null,
                    "sliders": hasCustomSliders ? {} : undefined,
                    "error_spans": [],
                    "textfield": null,
                }
                // Initialize all custom slider values to null
                if (response.info.sliders && response.info.sliders.length > 0) {
                    for (const slider of response.info.sliders!) {
                        result[model].sliders![slider.name] = null
                    }
                }
            }
            return result
        })
        $("#settings_comment").val("")
    }
    state.validations = data.map(item => item.validation)
    state.payload_items = data  // Store payload items to check skippable
    state.output_blocks = []
    state.action_log = [{ "time": Date.now() / 1000, "action": "load" }]
    state.has_unsaved_work = false
    state.skip_mode = false

    state.protocol = response.info.protocol
    state.protocol_error_spans = response.info.protocol == "ESA" || response.info.protocol == "cESA" || response.info.protocol == "MQM"
    state.protocol_error_categories = response.info.protocol == "MQM"

    // Use custom MQM categories if provided, otherwise use default
    if (response.info.mqm_categories) {
        // adding blanks
        state.mqm_categories = {
            "": [],
            ...Object.fromEntries(Object.entries(response.info.mqm_categories).map(([key, value]) => [key, ["", ...value]]))
        }

    } else {
        state.mqm_categories = MQM_ERROR_CATEGORIES
    }

    // check if slider_colors is not defined
    if (response.info.slider_colors === undefined && response.info.protocol == "cESA") {
        response.info.slider_colors = true
    }

    // Use custom MQM severities if provided, otherwise use default
    state.mqm_severities = response.info.mqm_severities ?? MQM_SEVERITIES

    // Set global instructions from payload
    if (response.info.instructions) {
        $("#instructions_global").html(response.info.instructions)
    } else {
        $("#instructions_global").html("")
    }

    $("#output_div").html("")

    for (let item_i = 0; item_i < data.length; item_i++) {
        let item = data[item_i]
        // character-level stuff won't work on media tags
        let no_src_char = !item.src || isMediaContent(item.src)
        let no_ref_char = !item.ref || isMediaContent(item.ref)

        let output_block = createOutputBlock(item, item_i, response.info)
        let src_chars_els = no_src_char || !item.src ? [] : output_block.find(".src_char").toArray()
        let ref_chars_els = no_ref_char || !item.ref ? [] : output_block.find(".ref_char").toArray()

        for (const [model, tgt] of Object.entries(item.tgt)) {
            let candidate_block = output_block.find(`.output_candidate[data-model='${CSS.escape(model)}']`)
            setupCandidateInteractions(candidate_block, item_i, model, tgt, response, src_chars_els, ref_chars_els, output_block)
        }

        // Source character hover effects
        if (!no_src_char && item.src) {
            src_chars_els.forEach((obj, i) => {
                $(obj).on("mouseleave", function () {
                    $(".src_char").removeClass("highlighted")
                    $(".ref_char").removeClass("highlighted")
                    $(".tgt_char").removeClass("highlighted")
                })

                $(obj).on("mouseenter", function () {
                    $(".ref_char").removeClass("highlighted")
                    $(".tgt_char").removeClass("highlighted")
                    if (state.settings.show_alignment) {
                        // Highlight corresponding characters in reference
                        if (ref_chars_els.length > 0) {
                            let ref_i = Math.round(i / src_chars_els.length * ref_chars_els.length)
                            for (let j = Math.max(0, ref_i - 5); j <= Math.min(ref_chars_els.length - 1, ref_i + 5); j++) {
                                $(ref_chars_els[j]).addClass("highlighted")
                            }
                        }
                        // Highlight corresponding characters in all candidates
                        output_block.find(".output_candidate").each(function () {
                            let tgt_chars = $(this).find(".tgt_char")
                            let tgt_i = Math.round(i / src_chars_els.length * tgt_chars.length)
                            for (let j = Math.max(0, tgt_i - 5); j <= Math.min(tgt_chars.length - 1, tgt_i + 5); j++) {
                                tgt_chars.eq(j).addClass("highlighted")
                            }
                        })
                    }
                })
            })
        }

        // Reference character hover effects
        if (!no_ref_char && item.ref) {
            ref_chars_els.forEach((obj, i) => {
                $(obj).on("mouseleave", function () {
                    $(".src_char").removeClass("highlighted")
                    $(".ref_char").removeClass("highlighted")
                    $(".tgt_char").removeClass("highlighted")
                })

                $(obj).on("mouseenter", function () {
                    $(".src_char").removeClass("highlighted")
                    $(".tgt_char").removeClass("highlighted")
                    if (state.settings.show_alignment) {
                        // Highlight corresponding characters in source
                        if (src_chars_els.length > 0) {
                            let src_i = Math.round(i / ref_chars_els.length * src_chars_els.length)
                            for (let j = Math.max(0, src_i - 5); j <= Math.min(src_chars_els.length - 1, src_i + 5); j++) {
                                $(src_chars_els[j]).addClass("highlighted")
                            }
                        }
                        // Highlight corresponding characters in all candidates
                        output_block.find(".output_candidate").each(function () {
                            let tgt_chars = $(this).find(".tgt_char")
                            let tgt_i = Math.round(i / ref_chars_els.length * tgt_chars.length)
                            for (let j = Math.max(0, tgt_i - 5); j <= Math.min(tgt_chars.length - 1, tgt_i + 5); j++) {
                                tgt_chars.eq(j).addClass("highlighted")
                            }
                        })
                    }
                })
            })
        }

        $("#output_div").append(output_block)
        state.output_blocks.push(output_block)
    }

    // Synchronize horizontal scroll across all output rows
    let isSyncingScroll = false
    const syncScroll = function (this: HTMLElement) {
        if (isSyncingScroll) return
        isSyncingScroll = true
        const scrollLeft = this.scrollLeft
        $(".output_scrollable").not(this).each(function () {
            const element = this as HTMLElement
            if (element.scrollLeft !== scrollLeft) {
                element.scrollLeft = scrollLeft
            }
        })
        isSyncingScroll = false
    }
    $(".output_scrollable").off("scroll.syncRows").on("scroll.syncRows", syncScroll)
    const firstOutputItem = $(".output_scrollable").get(0) as HTMLElement | undefined
    if (firstOutputItem) {
        syncScroll.call(firstOutputItem)
    }

    // trigger once to reposition toolboxes
    $(window).trigger('resize.toolbox')
    check_unlock()

    // Attach event listeners to multimedia elements for logging (no overhead if no audio/video present)
    // Note: Elements are removed when output_div is cleared, so no explicit cleanup needed
    $("#output_div audio, #output_div video").each(function () {
        const element = this as HTMLMediaElement
        const $parent = $(element).closest('.output_src, .output_ref, .output_tgt')
        const context = (
            $parent.hasClass('output_src') ? 'src' :
                $parent.hasClass('output_ref') ? 'ref' :
                    $parent.closest('.output_candidate').attr('data-model') || 'unknown'
        )

        $(element).on('play', () => {
            state.action_log.push({ "time": Date.now() / 1000, "action": "media_play", "media_src": element.src, "model": context, "media_time": element.currentTime })
        })

        $(element).on('pause', () => {
            state.action_log.push({ "time": Date.now() / 1000, "action": "media_pause", "media_src": element.src, "model": context, "media_time": element.currentTime })
        })

        $(element).on('seeked', () => {
            state.action_log.push({ "time": Date.now() / 1000, "action": "media_seek", "media_src": element.src, "model": context, "media_time": element.currentTime })
        })
    })


    $("#button_next").off("click")
    $("#button_next").on("click", async function () {
        // Perform validation unless in skip tutorial mode
        let validationResult: boolean[] | null = null
        if (!state.skip_mode) {
            validationResult = await performValidation()
            if (validationResult == null) {
                // validation failed, don't proceed
                return
            }
        }

        // disable while communicating with the server
        $("#button_next").attr("disabled", "disabled")
        $("#button_next").val("Next 📶")
        state.action_log.push({ "time": Date.now() / 1000, "action": "submit" + (state.skip_mode ? "_skip" : "") })

        // Build payload
        let payload_local: any = {
            "annotation": state.response_log,
            "actions": state.action_log,
            "item": response.payload,
        }

        if (!state.skip_mode && validationResult && validationResult.length > 0) {
            payload_local["validations"] = validationResult
        }

        // Include comment if provided
        const comment = $("#settings_comment").val() as string
        if (comment && comment.trim() !== "") {
            payload_local["comment"] = comment.trim()
            // Clear comment after submission
            $("#settings_comment").val("")
        }

        let outcome = await log_response(payload_local, response.info.item_i)
        if (outcome == null || outcome == false) {
            notify("Error submitting the annotations. Please try again.")
            $("#button_next").removeAttr("disabled")
            check_unlock()
            return
        }
        await display_next_item()
    })
}

/**
 * Display goodbye screen when all annotations are done
 */
function display_goodbye(response: DataGoodbye, navigate_to_item: (i: number | string) => void): void {
    // Use instructions_goodbye if provided, otherwise use default message
    // Note: instructions_goodbye may contain arbitrary HTML including variables that are replaced server-side

    $("#output_div").html(`
    <div class='white-box' style='width: max-content'>
    <h2>🎉 All done, thank you for your annotations!</h2>

    ${response.instructions_goodbye}
    <br>
    <br>
    </div>
    `)
    redrawProgress(null, response.progress_welcome, response.progress, navigate_to_item)
    $("#time").text(`Time: ${Math.round(response.time / 60)}m`)
    $("#button_next").prop("disabled", true)
    $("#button_next").val("Next 💯")
}


// Display form for collecting user information
function display_form(response: DataForm) {
    // Clear previous content and state
    $("#output_div").empty()
    state.response_log = []
    state.validations = []
    state.output_blocks = []
    state.action_log = [{ "time": Date.now() / 1000, "action": "load" }]

    redrawProgress(response.info.item_i, response.progress_welcome, response.progress, navigate_to_item)
    $("#progress").toggle(response.info.show_progress !== false)
    $("#time").text(`Time: ${Math.round(response.time / 60)}m`)

    // Display instructions if present
    if (response.info.instructions) {
        $("#instructions").html(response.info.instructions)
        $("#instructions").show()
    } else {
        $("#instructions").hide()
    }

    // Create form container
    const formContainer = $('<div class="form-container"></div>')

    // Store form responses (using Array.from for clarity)
    const formResponses: Array<string | number | null> = Array.from({ length: response.payload.length }, () => null)

    // Pre-fill if there are existing responses
    if (response.payload_existing?.annotation) {
        response.payload_existing.annotation.forEach((value, i) => {
            formResponses[i] = value
        })
    }

    // Create form fields
    response.payload.forEach((item, index) => {
        const fieldDiv = $('<div class="form-field"></div>')

        // Add the text/label
        const label = $(`<div class="form-label">${item.text}</div>`)
        fieldDiv.append(label)

        // Add input field based on form type
        if (item.form === "string") {
            const input = $('<input type="text" class="form-input" />')
            if (formResponses[index] !== null) {
                input.val(String(formResponses[index]))
            }
            input.on('input', function () {
                formResponses[index] = $(this).val() as string
                state.has_unsaved_work = true
                check_form_unlock(formResponses, response.payload)
            })
            fieldDiv.append(input)
        } else if (item.form === "number") {
            const input = $('<input type="number" class="form-input" />')
            if (formResponses[index] !== null) {
                input.val(Number(formResponses[index]))
            }
            input.on('input', function () {
                const val = $(this).val()
                formResponses[index] = val === "" ? null : Number(val)
                state.has_unsaved_work = true
                check_form_unlock(formResponses, response.payload)
            })
            fieldDiv.append(input)
        } else if (item.form === "choices" && item.choices) {
            const select = $('<select class="form-input"></select>')
            // Add default empty option if no value is selected
            if (formResponses[index] === null) {
                select.append('<option value="" disabled selected>Select an option</option>')
            }

            item.choices.forEach(choice => {
                const option = $(`<option value="${choice}">${choice}</option>`)
                if (formResponses[index] === choice) {
                    option.prop("selected", true)
                }
                select.append(option)
            })

            select.on('change', function () {
                const val = $(this).val() as string
                formResponses[index] = val
                state.has_unsaved_work = true
                check_form_unlock(formResponses, response.payload)
            })
            fieldDiv.append(select)
        } else if (item.form === "script" && item.script) {
            // Script is evaluated immediately and hidden from user view
            try {
                // Wrap in anonymous function as requested: "put the content of form.script into an anonymous function"
                const scriptFunc = new Function(item.script)
                const result = scriptFunc()
                formResponses[index] = result
            } catch (e) {
                console.error("Error executing form script:", e)
                formResponses[index] = "Error: " + String(e)
            }
        }

        formContainer.append(fieldDiv)
    })

    $("#output_div").append(formContainer)

    // Set up submit button
    $("#button_next").off("click")
    $("#button_next").on("click", async function () {
        // Disable button during submission
        $("#button_next").attr("disabled", "disabled")
        $("#button_next").val("Next 📶")

        state.action_log.push({ "time": Date.now() / 1000, "action": "submit" })

        // Build payload with proper typing
        const payload_local: {
            annotation: Array<string | number | null>,
            actions: Array<any>,
            item: Array<DataFormItem>,
            comment?: string
        } = {
            "annotation": formResponses,
            "actions": state.action_log,
            "item": response.payload,
        }

        // Include comment if provided
        const comment = $("#settings_comment").val() as string
        if (comment && comment.trim() !== "") {
            payload_local.comment = comment.trim()
            // Clear comment after submission
            $("#settings_comment").val("")
        }

        // Log the form responses
        let outcome = await log_response(payload_local, response.info.item_i)

        if (outcome == null || outcome == false) {
            notify("Error submitting the form. Please try again.")
            $("#button_next").removeAttr("disabled")
            check_form_unlock(formResponses, response.payload)
            return
        }

        state.has_unsaved_work = false
        state.action_log = []

        // Move to next item
        display_next_item()
    })

    check_form_unlock(formResponses, response.payload)
}

// Check if form can be submitted (all required fields filled)
function check_form_unlock(responses: Array<string | number | null>, payload: Array<DataFormItem>) {
    if (frozenMode) {
        $("#button_next").attr("disabled", "disabled")
        $("#button_next").val("Next 🔒")
        return
    }

    // Check if all form fields (non-null form type) are filled
    for (let i = 0; i < payload.length; i++) {
        if (payload[i].form !== null) {
            const response = responses[i]
            // Check if response is null or empty string
            if (response === null || response === "") {
                $("#button_next").attr("disabled", "disabled")
                $("#button_next").val("Next 🚧")
                return
            }
        }
    }

    // All required fields are filled
    $("#button_next").removeAttr("disabled")
    $("#button_next").val("Next ✅")
}



async function navigate_to_item(item_i: number | string) {
    // Warn if there's unsaved work
    if (state.has_unsaved_work) {
        if (!confirm("You have unsaved work. Are you sure you want to navigate away?")) {
            return
        }
    }

    // Fetch and display a specific item by index
    let response = await get_i_item<DataPayload | DataGoodbye | DataForm>(item_i)
    state.has_unsaved_work = false

    if (response == null) {
        notify("Error fetching the item. Please try again later.")
        return
    }

    // clear previous handler
    $("#button_next").off("click")
    if (response.status == "goodbye") {
        display_goodbye(response as DataGoodbye, navigate_to_item)
    } else if (response.status == "form") {
        display_form(response as DataForm)
    } else if (response.status == "ok") {
        display_next_payload(response as DataPayload)
    } else {
        console.error("Non-ok response", response)
    }
}

async function display_next_item() {
    let response = await get_next_item<DataPayload | DataGoodbye | DataForm>()
    state.has_unsaved_work = false

    if (response == null) {
        notify("Error fetching the next item. Please try again later.")
        return
    }

    if (response.status == "goodbye") {
        display_goodbye(response as DataGoodbye, navigate_to_item)
    } else if (response.status == "form") {
        display_form(response as DataForm)
    } else if (response.status == "ok") {
        display_next_payload(response as DataPayload)
    } else {
        console.error("Non-ok response", response)
    }
}

/**
 * Validate all responses and handle failures
 * Returns true if validation passes or is skipped, false if it fails
 */
async function performValidation(): Promise<Array<boolean> | null> {
    $(".validation_warning").remove()

    let results: Array<boolean> = []

    // Validate each item and each model
    for (let item_ij = 0; item_ij < state.response_log.length; item_ij++) {
        let results_local = []
        const modelNames = Object.keys(state.response_log[item_ij])

        for (let model of modelNames) {
            if (state.validations[item_ij] == undefined) {
                continue
            }
            // Use validateResponse to support score_greaterthan conditions
            const result = validateResponse(state.response_log[item_ij], state.validations[item_ij]!, model)


            // if we fail and there's a message, prevent loading next item and show warning
            if (!result && state.validations[item_ij]![model]?.warning) {
                // Scroll to the block
                if (state.output_blocks[item_ij] && state.output_blocks[item_ij].offset()) {
                    $('html, body').animate({ scrollTop: state.output_blocks[item_ij].offset()!.top - 100 }, 500)
                }
                // Show warning indicator
                state.output_blocks[item_ij].find(".validation_warning").remove()
                const warningEl = $(`<span class="validation_warning" title="${state.validations[item_ij]![model]?.warning || 'Validation failed'}">⚠️</span>`)
                state.output_blocks[item_ij].find(".instructions_message").append(warningEl)
                notify(state.validations[item_ij]![model]!.warning as string)
                return null
            }

            results_local.push(result)
        }
        // check if all models passed
        if (results_local.length > 0) results.push(results_local.every(r => r))
    }

    // TODO: log this incident

    return results
}

// Skip tutorial button handler
$("#button_skip").on("click", function () {
    state.skip_mode = true
    notify("Skipping. Your current annotations will be submitted.")
    // Trigger the next button click
    $("#button_next").trigger("click")
})

display_next_item()

// toggle settings display
$("#button_settings").on("click", function () {
    $("#settings_div").toggle()
})

// load settings from localStorage
$("#settings_approximate_alignment").on("change", function () {
    state.settings.show_alignment = $("#settings_approximate_alignment").is(":checked")
    localStorage.setItem("setting_approximate_alignment", state.settings.show_alignment.toString())
})
if (localStorage.getItem("setting_approximate_alignment") != null) {
    state.settings.show_alignment = localStorage.getItem("setting_approximate_alignment") == "true"
}
$("#settings_approximate_alignment").prop("checked", state.settings.show_alignment)
$("#settings_approximate_alignment").trigger("change")

// word-level annotation setting
$("#settings_word_level").on("change", function () {
    state.settings.word_level = $("#settings_word_level").is(":checked")
    localStorage.setItem("setting_word_level", state.settings.word_level.toString())
})
if (localStorage.getItem("setting_word_level") != null) {
    state.settings.word_level = localStorage.getItem("setting_word_level") == "true"
}
$("#settings_word_level").prop("checked", state.settings.word_level)
$("#settings_word_level").trigger("change")

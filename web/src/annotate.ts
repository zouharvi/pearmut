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
    hasAllowSkip,
    DataGoodbye,
    ProtocolInfo,
    SliderConfig,
    displayGoodbyeScreen,
    isMediaContent,
    contentToCharSpans,
    isSpanComplete,
    computeWordBoundaries,
    detectTextDirection,
    debounce,
    isFormItem,
    renderFormItem,
    collectFormData,
    areFormFieldsComplete,
    FormResponse,
} from './utils';

// Check if frozen mode is enabled (view-only, no annotations)
const searchParams = new URLSearchParams(window.location.search)
const frozenMode = searchParams.has("frozen")

// Each model has its own response
type CandidateResponse = {
    score: number | null,  // Main score, always present
    sliders?: Record<string, number | null>,  // Optional custom sliders
    error_spans: Array<ErrorSpan>,
    textfield?: string | null,  // Optional textfield content
}
// Response for a document with multiple models - keyed by model name
type DocumentResponse = Record<string, CandidateResponse>

// Form item response type
type FormItemResponse = FormResponse

// Item can be either a regular annotation item or a form item (string)
type PayloadItem = {
    src?: string,  // Optional source text
    ref?: string,  // Optional reference text
    tgt: Record<string, string>,  // Dictionary of model->translation
    checks?: any,
    instructions?: string,
    error_spans?: Record<string, Array<ErrorSpan>>,  // Pre-filled error spans keyed by model name
    validation?: Record<string, Validation> | undefined,  // Validation rules keyed by model name
} | string  // Form item is just a string containing HTML

type DataPayload = {
    status: string,
    progress: Array<boolean>,
    time: number,
    payload: Array<PayloadItem>,
    payload_existing?: {
        annotation: Array<DocumentResponse | FormItemResponse>,
        comment?: string
    },
    info: ProtocolInfo
}

/**
 * Gets error spans for a specific model
 */
function getErrorSpansForModel(error_spans: Record<string, Array<ErrorSpan>> | undefined, model: string): Array<ErrorSpan> {
    if (!error_spans) return []
    return error_spans[model] || []
}

let response_log: Array<DocumentResponse | FormItemResponse> = []
let action_log: Array<any> = []
let validations: Array<Record<string, Validation> | undefined> = []
let output_blocks: Array<JQuery<HTMLElement>> = []
let settings_show_alignment = true
let settings_word_level = false
let has_unsaved_work = false
let skip_tutorial_mode = false
// Protocol settings for check_unlock
let protocol_error_spans = false
let protocol_error_categories = false

// Prevent accidental refresh/navigation when there is ongoing work
window.addEventListener('beforeunload', (event) => {
    if (has_unsaved_work) {
        event.preventDefault()
        event.returnValue = ''
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
        return
    }

    // Check if there are any form items with required fields
    if ($(".output_block.form-item").length > 0) {
        if (!areFormFieldsComplete()) {
            $("#button_next").attr("disabled", "disabled")
            $("#button_next").val("Next 🚧")
            return
        }
        // If we only have form items, enable the button
        if ($(".output_candidate").length === 0) {
            $("#button_next").removeAttr("disabled")
            $("#button_next").val("Next ✅")
            return
        }
    }

    // Check if all error spans are complete (have required severity and category based on protocol)
    if (protocol_error_spans || protocol_error_categories) {
        for (const doc_responses of response_log) {
            // Skip form item responses
            if (typeof doc_responses === 'object' && !Array.isArray(doc_responses)) {
                // Check if it's a DocumentResponse (has model keys with CandidateResponse values)
                const values = Object.values(doc_responses)
                if (values.length > 0 && values[0] && typeof values[0] === 'object' && 'error_spans' in values[0]) {
                    for (const r of values as CandidateResponse[]) {
                        for (const span of r.error_spans) {
                            if (!isSpanComplete(span, protocol_error_categories)) {
                                $("#button_next").attr("disabled", "disabled")
                                $("#button_next").val("Next 🚧")
                                return
                            }
                        }
                    }
                }
            }
        }
    }

    // Check if all scores are set
    let all_done = response_log.every(doc_responses => {
        // Form items don't need scores
        if (typeof doc_responses === 'object' && !Array.isArray(doc_responses)) {
            const values = Object.values(doc_responses)
            // Empty object or FormItemResponse (doesn't have error_spans)
            if (values.length === 0 || (values[0] && typeof values[0] !== 'object') || !('error_spans' in values[0])) {
                return true
            }
            // DocumentResponse - check scores
            return values.every((r: any) => {
                if (r.sliders) {
                    // Custom sliders mode: all sliders must be non-null (no score required)
                    // Note: when sliders is {} (empty, from sliders: []), Object.values returns []
                    // and every() returns true (vacuous truth), allowing immediate progression
                    return Object.values(r.sliders).every(val => val !== null)
                } else {
                    // Single score mode: the score must be set
                    return r.score != null
                }
            })
        }
        return true
    })
    if (!all_done) {
        $("#button_next").attr("disabled", "disabled")
        $("#button_next").val("Next 🚧")
        return
    }

    $("#button_next").removeAttr("disabled")
    $("#button_next").val("Next ✅")
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
        return `
        <div class="output_response">
          <input type="range" min="0" max="100" value="-1" id="response_${item_i}_${model}">
          <span class="slider_label">❓/100</span>
        </div>
        `
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

/**
 * Check if a response is a form item response (not a DocumentResponse)
 */
function isFormItemResponse(response: DocumentResponse | FormItemResponse): boolean {
    if (typeof response !== 'object' || Object.keys(response).length === 0) {
        return true
    }
    const firstValue = Object.values(response)[0]
    return typeof firstValue !== 'object' || !('error_spans' in firstValue)
}

async function display_next_payload(response: DataPayload) {
    // Cleanup toolboxes and handlers from previous item
    cleanupPreviousItem()

    redrawProgress(response.info.item_i, response.progress, navigate_to_item)
    $("#time").text(`Time: ${Math.round(response.time / 60)}m`)

    let data = response.payload
    // Initialize response log - use payload_existing if available
    if (response.payload_existing) {
        response_log = response.payload_existing.annotation.map(docResponses => {
            // Check if it's a form item response
            if (isFormItemResponse(docResponses)) {
                return docResponses as FormItemResponse
            }
            // Otherwise it's a DocumentResponse
            const result: DocumentResponse = {}
            for (const [model, r] of Object.entries(docResponses)) {
                result[model] = {
                    "score": (r as any).score,
                    "sliders": (r as any).sliders ? { ...(r as any).sliders } : undefined,
                    "error_spans": (r as any).error_spans ? [...(r as any).error_spans] : [],
                    "textfield": (r as any).textfield ?? null,
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
        response_log = data.map(item => {
            // Check if item is a form item (string)
            if (isFormItem(item)) {
                return {} as FormItemResponse  // Will be filled when Next button is clicked
            }
            // Regular annotation item
            const result: DocumentResponse = {}
            for (const model of Object.keys((item as any).tgt)) {
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
    validations = data.map(item => isFormItem(item) ? undefined : (item as Exclude<PayloadItem, string>).validation)
    output_blocks = []
    action_log = [{ "time": Date.now() / 1000, "action": "load" }]
    has_unsaved_work = false
    skip_tutorial_mode = false

    // Show/hide skip tutorial button based on validation settings
    if (hasAllowSkip(validations)) {
        $("#button_skip_tutorial").show()
    } else {
        $("#button_skip_tutorial").hide()
    }

    protocol_error_spans = response.info.protocol == "ESA" || response.info.protocol == "MQM"
    protocol_error_categories = response.info.protocol == "MQM"

    // Set global instructions from payload
    if (response.info.instructions) {
        $("#instructions_global").html(response.info.instructions)
    } else {
        $("#instructions_global").html("")
    }

    $("#output_div").html("")

    for (let item_i = 0; item_i < data.length; item_i++) {
        let item = data[item_i]
        
        // Check if this is a form item (simple string)
        if (isFormItem(item)) {
            const formBlock = renderFormItem(item as string, item_i)
            $("#output_div").append(formBlock)
            output_blocks.push(formBlock)
            
            // Add event listeners to form fields to trigger check_unlock
            formBlock.find("input, select, textarea").on("change input", () => {
                check_unlock()
            })
            
            continue  // Skip regular item rendering
        }
        
        // Cast to regular item type
        const regularItem = item as Exclude<PayloadItem, string>
        
        // character-level stuff won't work on media tags
        let no_src_char = !regularItem.src || isMediaContent(regularItem.src)
        let no_ref_char = !regularItem.ref || isMediaContent(regularItem.ref)

        // Detect text direction for source and reference
        let src_dir = regularItem.src && !no_src_char ? detectTextDirection(regularItem.src) : 'ltr'
        let ref_dir = regularItem.ref && !no_ref_char ? detectTextDirection(regularItem.ref) : 'ltr'

        // Build character spans for source and reference
        let src_chars = ""
        if (regularItem.src) {
            src_chars = no_src_char ? regularItem.src : contentToCharSpans(regularItem.src, "src_char")
        }
        let ref_chars = ""
        if (regularItem.ref) {
            ref_chars = no_ref_char ? regularItem.ref : contentToCharSpans(regularItem.ref, "ref_char")
        }

        // Build source and reference boxes - only if they exist
        let srcRefBoxes = ""
        if (regularItem.src) {
            let src_style = src_dir === 'rtl' ? ' style="direction: rtl;"' : ''
            srcRefBoxes += `<div class="output_src"${src_style}>${src_chars}</div>`
        }
        if (regularItem.ref) {
            let ref_style = ref_dir === 'rtl' ? ' style="direction: rtl;"' : ''
            srcRefBoxes += `<div class="output_ref"${ref_style}>${ref_chars}</div>`
        }

        let output_block = $(`
        <div class="output_block">
          <span class="instructions_message"></span>
          <div class="output_item">
            ${srcRefBoxes}
          </div>
        </div>
        `)

        if (regularItem.instructions) {
            output_block.find(".instructions_message").html(regularItem.instructions)
        }

        // Add each model's output
        let src_chars_els = no_src_char || !regularItem.src ? [] : output_block.find(".src_char").toArray()
        let ref_chars_els = no_ref_char || !regularItem.ref ? [] : output_block.find(".ref_char").toArray()

        for (const [model, tgt] of Object.entries(regularItem.tgt)) {
            // Type-safe accessor for response_log in this regular item context
            const currentResponse = response_log[item_i] as DocumentResponse
            
            let no_tgt_char = isMediaContent(tgt)
            let tgt_dir = !no_tgt_char ? detectTextDirection(tgt) : 'ltr'
            let tgt_chars = no_tgt_char ? tgt : (contentToCharSpans(tgt, "tgt_char") + (protocol_error_spans ? ' <span class="tgt_char char_missing">[missing]</span>' : ""))
            let tgt_style = tgt_dir === 'rtl' ? ' style="direction: rtl;"' : ''

            let candidate_block = $(`
            <div class="output_candidate" data-candidate="${model}" data-model="${model}">
              <div class="output_tgt"${tgt_style}>${tgt_chars}</div>
              ${_slider_html(item_i, model, response.info.sliders)}
            </div>
            `)

            // Add model name at the top of the candidate block if enabled
            if (response.info.show_model_names) {
                let model_name_div = $('<div class="model_name"></div>').text(model)
                candidate_block.prepend(model_name_div)
            }

            candidate_block.find(".output_response").prepend(_textfield_button_html(item_i, model, response.info.textfield))
            candidate_block.append(_textfield_html(item_i, model, response.info.textfield))

            output_block.find(".output_item").append(candidate_block)

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
            let missing_i = protocol_error_spans ? tgt_chars_objs.findIndex(obj => obj.el.hasClass("char_missing")) : -1

            if (!no_tgt_char) {
                tgt_chars_objs.forEach((obj, i) => {
                    let is_missing = (i == missing_i)

                    // leaving target character
                    $(obj.el).on("mouseleave", function () {
                        $(".src_char").removeClass("highlighted")
                        $(".ref_char").removeClass("highlighted")
                        $(".tgt_char").removeClass("highlighted")
                        $(".tgt_char").removeClass("highlighted_active")

                        // highlight corresponding toolbox if error severity is set
                        if (obj.error_span != null && obj.error_span.severity != null && (!protocol_error_categories || (obj.error_span.category != null && obj.error_span.category?.includes("/")))) {
                            tgt_chars_objs[i].toolbox?.css("display", "none")
                        }
                    })

                    // entering target character
                    $(obj.el).on("mouseenter", function () {
                        $(".src_char").removeClass("highlighted")
                        $(".ref_char").removeClass("highlighted")
                        $(".tgt_char").removeClass("highlighted")
                        if (settings_show_alignment && !is_missing) {
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
                            if (settings_word_level && state_i != missing_i) {
                                preview_left = tgt_chars_objs[preview_left].word_start
                                preview_right = tgt_chars_objs[preview_right].word_end
                            }
                            for (let j = preview_left; j <= preview_right; j++) {
                                $(tgt_chars_objs[j].el).addClass("highlighted")
                            }
                        } else if (settings_word_level && !is_missing && state_i == null) {
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

                            tgt_chars_objs[span.start_i].toolbox?.css("display", "block")
                        }
                    })

                    // add spans and toolbox only in case the protocol asks for it
                    if (protocol_error_spans || protocol_error_categories) {
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
                                if (settings_word_level && !is_missing && state_i != missing_i) {
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

                                if (currentResponse[model].error_spans.some(span => {
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
                                    protocol_error_categories,
                                    error_span,
                                    tgt_chars_objs,
                                    left_i,
                                    right_i,
                                    () => {
                                        // onDelete callback
                                        currentResponse[model].error_spans = currentResponse[model].error_spans.filter(span => span != error_span)
                                        action_log.push({ "time": Date.now() / 1000, "action": "delete_span", "index": item_i, "model": model, "start_i": left_i, "end_i": right_i })
                                        has_unsaved_work = true
                                    },
                                    frozenMode
                                )

                                $("body").append(toolbox)
                                check_unlock()

                                // handle hover on toolbox
                                toolbox.on("mouseenter focusin contextmenu", function (e) {
                                    if (e.type === "contextmenu") e.preventDefault();
                                    toolbox.css("display", "block")
                                    check_unlock()
                                })
                                // handle hover on toolbox
                                toolbox.on("mouseleave focusout", function () {
                                    // hide if severity is set for ESA or both severity and category are set for MQM
                                    if (error_span.severity != null && (!protocol_error_categories || (error_span.category != null && error_span.category?.includes("/")))) {
                                        toolbox.css("display", "none")
                                        check_unlock()
                                    }
                                })

                                // set up callback to reposition toolbox on resize         
                                $(window).on('resize.toolbox', () => updateToolboxPosition(toolbox, $(tgt_chars_objs[left_i].el)))
                                updateToolboxPosition(toolbox, $(tgt_chars_objs[left_i].el))

                                // store error span
                                currentResponse[model].error_spans.push(error_span)
                                action_log.push({ "time": Date.now() / 1000, "action": "create_span", "index": item_i, "model": model, "start_i": left_i, "end_i": right_i })
                                has_unsaved_work = true
                                for (let j = left_i; j <= right_i; j++) {
                                    $(tgt_chars_objs[j].el).addClass("error_unknown")
                                    tgt_chars_objs[j].toolbox = toolbox
                                    tgt_chars_objs[j].error_span = error_span
                                }
                            } else {
                                // check if we are in existing span
                                if (currentResponse[model].error_spans.some(span => i >= span.start_i && i <= span.end_i)) {
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

            // Load error spans - use payload_existing if available, otherwise use regularItem.error_spans
            const existingAnnotation = response.payload_existing?.annotation[item_i]
            const existingErrorSpans = existingAnnotation && typeof existingAnnotation === 'object' && model in existingAnnotation ? (existingAnnotation as any)[model]?.error_spans : undefined
            const candidateSpans = existingErrorSpans || getErrorSpansForModel(regularItem.error_spans, model)

            if (!no_tgt_char && (protocol_error_spans || protocol_error_categories) && candidateSpans.length > 0) {
                // Only reset if loading from payload_existing (to avoid duplicating pre-filled spans)
                if (existingErrorSpans) {
                    currentResponse[model].error_spans = []
                }

                for (const prefilled of candidateSpans) {
                    const left_i = prefilled.start_i, right_i = prefilled.end_i
                    if (left_i < 0 || right_i >= tgt_chars_objs.length || left_i > right_i) continue
                    let error_span: ErrorSpan = { ...prefilled }
                    currentResponse[model].error_spans.push(error_span)

                    let toolbox = createSpanToolbox(protocol_error_categories, error_span, tgt_chars_objs, left_i, right_i, () => {
                        currentResponse[model].error_spans = currentResponse[model].error_spans.filter(s => s != error_span)
                        action_log.push({ "time": Date.now() / 1000, "action": "delete_span", "index": item_i, "model": model, "start_i": left_i, "end_i": right_i })
                        has_unsaved_work = true
                    }, frozenMode)
                    $("body").append(toolbox)
                    toolbox.on("mouseenter", () => { toolbox.css("display", "block"); check_unlock() })
                    toolbox.on("mouseleave", () => {
                        if (error_span.severity != null && (!protocol_error_categories || (error_span.category != null && error_span.category?.includes("/")))) {
                            toolbox.css("display", "none"); check_unlock()
                        }
                    })
                    $(window).on('resize.toolbox', () => updateToolboxPosition(toolbox, $(tgt_chars_objs[left_i].el)))

                    for (let j = left_i; j <= right_i; j++) {
                        $(tgt_chars_objs[j].el).addClass(error_span.severity ? `error_${error_span.severity}` : "error_unknown")
                        tgt_chars_objs[j].toolbox = toolbox
                        tgt_chars_objs[j].error_span = error_span
                    }
                    if (error_span.severity != null && (!protocol_error_categories || (error_span.category != null && error_span.category?.includes("/")))) {
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
                    let slider = candidate_block.find(`input[data-slider="${sliderName}"]`)
                    let label = candidate_block.find(`.slider_label[data-slider="${sliderName}"]`)

                    slider.on("click input", function () {
                        // In frozen mode, do not allow changing scores
                        if (frozenMode) return

                        let val = parseInt((<HTMLInputElement>this).value)
                        label.text(`${val}/${sliderMax}`)

                        // Store in sliders field
                        if (currentResponse[model].sliders![sliderName] == null) {
                            currentResponse[model].sliders![sliderName] = val
                            has_unsaved_work = true
                            check_unlock()
                            action_log.push({ "time": Date.now() / 1000, "action": sliderName, "index": item_i, "model": model, "value": val })
                        }
                    })

                    slider.on("change", function () {
                        // In frozen mode, do not allow changing scores
                        if (frozenMode) return

                        let val = parseInt((<HTMLInputElement>this).value)
                        label.text(`${val}/${sliderMax}`)

                        // Store in sliders field
                        currentResponse[model].sliders![sliderName] = val
                        action_log.push({ "time": Date.now() / 1000, "action": sliderName, "index": item_i, "model": model, "value": val })
                        has_unsaved_work = true
                        check_unlock()
                    })

                    // Disable slider in frozen mode
                    if (frozenMode) {
                        slider.prop("disabled", true)
                    }

                    // Pre-fill score from payload_existing if available
                    let existingScore: number | null = null
                    const existingAnnotation2 = response.payload_existing?.annotation[item_i]
                    existingScore = existingAnnotation2 && typeof existingAnnotation2 === 'object' && model in existingAnnotation2 ? (existingAnnotation2 as any)[model]?.sliders?.[sliderName] ?? null : null

                    if (existingScore != null) {
                        slider.val(existingScore)
                        label.text(`${existingScore}/${sliderMax}`)
                        currentResponse[model].sliders![sliderName] = existingScore
                    }
                }
            } else if (!hasNoSliders) {
                // Single slider mode (default Score slider)
                let slider = candidate_block.find("input[type='range']")
                let label = candidate_block.find(".slider_label")
                slider.on("click input", function () {
                    // In frozen mode, do not allow changing scores
                    if (frozenMode) return

                    let val = parseInt((<HTMLInputElement>this).value)
                    label.text(`${val}/100`)

                    if (currentResponse[model].score == null) {
                        currentResponse[model].score = val
                        has_unsaved_work = true
                        check_unlock()
                        action_log.push({ "time": Date.now() / 1000, "action": "score", "index": item_i, "model": model, "value": val })
                    }
                })
                slider.on("change", function () {
                    // In frozen mode, do not allow changing scores
                    if (frozenMode) return

                    let val = parseInt((<HTMLInputElement>this).value)
                    label.text(`${val}/100`)
                    currentResponse[model].score = val
                    has_unsaved_work = true
                    check_unlock()
                    // push only for change which happens just once
                    action_log.push({ "time": Date.now() / 1000, "action": "score", "index": item_i, "model": model, "value": val })
                })

                // Disable slider in frozen mode
                if (frozenMode) {
                    slider.prop("disabled", true)
                }

                // Pre-fill score from payload_existing if available
                const existingAnnotation3 = response.payload_existing?.annotation[item_i]
                const existingScore = existingAnnotation3 && typeof existingAnnotation3 === 'object' && model in existingAnnotation3 ? (existingAnnotation3 as any)[model]?.score : undefined
                if (existingScore != null) {
                    slider.val(existingScore)
                    label.text(`${existingScore}/100`)
                    currentResponse[model].score = existingScore
                }
            }

            // Setup textfield if enabled
            if (response.info.textfield) {
                const textfield = candidate_block.find(`#textfield_${item_i}_${model}`)
                const toggle = candidate_block.find(`#textfield_toggle_${item_i}_${model}`)

                // Pre-fill with model output if mode is "prefilled"
                // Note: tgt is from trusted campaign data, jQuery .val() safely escapes any content
                if (response.info.textfield === "prefilled") {
                    textfield.val(tgt)
                    currentResponse[model].textfield = tgt
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
                    action_log.push({ "time": Date.now() / 1000, "action": "textfield", "index": item_i, "model": model, "value": val })
                }, 500)

                textfield.on("input", function () {
                    // In frozen mode, do not allow changing textfield
                    if (frozenMode) return

                    let val = (<HTMLTextAreaElement>this).value
                    currentResponse[model].textfield = val
                    has_unsaved_work = true
                    // Log with debounce to avoid excessive logging during typing
                    logTextfieldInput()
                })

                // Disable textfield in frozen mode
                if (frozenMode) {
                    textfield.prop("disabled", true)
                }

                // Pre-fill textfield from payload_existing if available (overrides prefilled mode)
                const existingAnnotation4 = response.payload_existing?.annotation[item_i]
                const existingTextfield = existingAnnotation4 && typeof existingAnnotation4 === 'object' && model in existingAnnotation4 ? (existingAnnotation4 as any)[model]?.textfield : undefined
                if (existingTextfield != null) {
                    textfield.val(existingTextfield)
                    currentResponse[model].textfield = existingTextfield
                }
            }
        }

        // Source character hover effects
        if (!no_src_char && regularItem.src) {
            src_chars_els.forEach((obj, i) => {
                $(obj).on("mouseleave", function () {
                    $(".src_char").removeClass("highlighted")
                    $(".ref_char").removeClass("highlighted")
                    $(".tgt_char").removeClass("highlighted")
                })

                $(obj).on("mouseenter", function () {
                    $(".ref_char").removeClass("highlighted")
                    $(".tgt_char").removeClass("highlighted")
                    if (settings_show_alignment) {
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
        if (!no_ref_char && regularItem.ref) {
            ref_chars_els.forEach((obj, i) => {
                $(obj).on("mouseleave", function () {
                    $(".src_char").removeClass("highlighted")
                    $(".ref_char").removeClass("highlighted")
                    $(".tgt_char").removeClass("highlighted")
                })

                $(obj).on("mouseenter", function () {
                    $(".src_char").removeClass("highlighted")
                    $(".tgt_char").removeClass("highlighted")
                    if (settings_show_alignment) {
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
        output_blocks.push(output_block)
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
            action_log.push({ "time": Date.now() / 1000, "action": "media_play", "media_src": element.src, "model": context, "media_time": element.currentTime })
        })

        $(element).on('pause', () => {
            action_log.push({ "time": Date.now() / 1000, "action": "media_pause", "media_src": element.src, "model": context, "media_time": element.currentTime })
        })

        $(element).on('seeked', () => {
            action_log.push({ "time": Date.now() / 1000, "action": "media_seek", "media_src": element.src, "model": context, "media_time": element.currentTime })
        })
    })
}


let payload: DataPayload | null = null

async function navigate_to_item(item_i: number) {
    // Warn if there's unsaved work
    if (has_unsaved_work) {
        if (!confirm("You have unsaved work. Are you sure you want to navigate away?")) {
            return
        }
    }

    // Fetch and display a specific item by index
    let response = await get_i_item<DataPayload | DataGoodbye>(item_i)
    has_unsaved_work = false

    if (response == null) {
        notify("Error fetching the item. Please try again later.")
        return
    }

    if (response.status == "goodbye") {
        displayGoodbyeScreen(response as DataGoodbye, navigate_to_item)
    } else if (response.status == "ok") {
        payload = response as DataPayload
        display_next_payload(response as DataPayload)
    } else {
        console.error("Non-ok response", response)
    }
}

async function display_next_item() {
    let response = await get_next_item<DataPayload | DataGoodbye>()
    has_unsaved_work = false

    if (response == null) {
        notify("Error fetching the next item. Please try again later.")
        return
    }

    if (response.status == "goodbye") {
        displayGoodbyeScreen(response as DataGoodbye, navigate_to_item)
    } else if (response.status == "ok") {
        payload = response as DataPayload
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
    for (let item_ij = 0; item_ij < response_log.length; item_ij++) {
        let results_local = []
        const itemResponse = response_log[item_ij]
        
        // Skip form items - they don't need validation
        if (isFormItemResponse(itemResponse)) {
            continue
        }
        
        const modelNames = Object.keys(itemResponse)

        for (let model of modelNames) {
            if (validations[item_ij] == undefined) {
                continue
            }
            // Use validateResponse to support score_greaterthan conditions
            const result = validateResponse(itemResponse as Record<string, any>, validations[item_ij]!, model)


            // if we fail and there's a message, prevent loading next item and show warning
            if (!result && validations[item_ij]![model]?.warning) {
                // Scroll to the block
                if (output_blocks[item_ij] && output_blocks[item_ij].offset()) {
                    $('html, body').animate({ scrollTop: output_blocks[item_ij].offset()!.top - 100 }, 500)
                }
                // Show warning indicator
                output_blocks[item_ij].find(".validation_warning").remove()
                const warningEl = $(`<span class="validation_warning" title="${validations[item_ij]![model]?.warning || 'Validation failed'}">⚠️</span>`)
                output_blocks[item_ij].find(".instructions_message").append(warningEl)
                notify(validations[item_ij]![model]!.warning as string)
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

$("#button_next").on("click", async function () {
    // Collect form data if there are form items
    const formData = collectFormData()
    if (formData.length > 0) {
        // Update response_log with form data
        let formIndex = 0
        for (let i = 0; i < response_log.length; i++) {
            // Check if this is a form item response
            if (isFormItemResponse(response_log[i])) {
                if (formIndex < formData.length) {
                    response_log[i] = formData[formIndex]
                    formIndex++
                }
            }
        }
    }
    
    // Perform validation unless in skip tutorial mode
    let validationResult;
    if (!skip_tutorial_mode) {
        validationResult = await performValidation()
        if (validationResult == null) {
            // validation failed, don't proceed
            return
        }
    }

    // disable while communicating with the server
    $("#button_next").attr("disabled", "disabled")
    $("#button_next").val("Next 📶")
    action_log.push({ "time": Date.now() / 1000, "action": "submit" + (skip_tutorial_mode ? "_skip" : "") })

    let payload_local = { "annotation": response_log, "actions": action_log, "item": payload?.payload, }
    if (!skip_tutorial_mode && validationResult!.length > 0) {
        // @ts-ignore
        payload_local["validations"] = validationResult
    }

    // Include comment if provided
    const comment = $("#settings_comment").val() as string
    if (comment && comment.trim() !== "") {
        // @ts-ignore
        payload_local["comment"] = comment.trim()
        // Clear comment after submission
        $("#settings_comment").val("")
    }

    let outcome = await log_response(payload_local, payload!.info.item_i)
    if (outcome == null || outcome == false) {
        notify("Error submitting the annotations. Please try again.")
        $("#button_next").removeAttr("disabled")
        $("#button_next").val("Next ❓")
        return
    }
    await display_next_item()
})

// Skip tutorial button handler
$("#button_skip_tutorial").on("click", function () {
    skip_tutorial_mode = true
    notify("Tutorial skipped. Your current annotations will be submitted.")
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
    settings_show_alignment = $("#settings_approximate_alignment").is(":checked")
    localStorage.setItem("setting_approximate_alignment", settings_show_alignment.toString())
})
if (localStorage.getItem("setting_approximate_alignment") != null) {
    settings_show_alignment = localStorage.getItem("setting_approximate_alignment") == "true"
}
$("#settings_approximate_alignment").prop("checked", settings_show_alignment)
$("#settings_approximate_alignment").trigger("change")

// word-level annotation setting
$("#settings_word_level").on("change", function () {
    settings_word_level = $("#settings_word_level").is(":checked")
    localStorage.setItem("setting_word_level", settings_word_level.toString())
})
if (localStorage.getItem("setting_word_level") != null) {
    settings_word_level = localStorage.getItem("setting_word_level") == "true"
}
$("#settings_word_level").prop("checked", settings_word_level)
$("#settings_word_level").trigger("change")

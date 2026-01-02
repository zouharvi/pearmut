import $ from 'jquery';

export function notify(message: string): void {
    /**
     * Displays a temporary notification message at the top center of the webpage.
     * The notification disappears after 4 seconds.
     * @param message - The message to be displayed in the notification.
     **/
    const notification = $('<div></div>')
        .html(message)
        .css({
            position: 'fixed',
            top: '10px',
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            color: 'white',
            padding: '10px 20px',
            borderRadius: '5px',
            zIndex: '1000'
        })
        .appendTo('body');

    setTimeout(() => {
        notification.remove();
    }, 4000);
}

// Shared types for error span annotation
export type ErrorSpan = { start_i: number, end_i: number, category: string | null, severity: string | null }
export type Response = { score: number | null, error_spans: Array<ErrorSpan> }
export type CharData = { el: JQuery<HTMLElement>, toolbox: JQuery<HTMLElement> | null, error_span: ErrorSpan | null, word_start: number, word_end: number }

/**
 * Check if an error span is complete (has required fields set based on protocol).
 * For MQM protocol, category must contain "/" to indicate both main category and subcategory are set.
 * For ESA protocol (no categories), only severity is required.
 */
export function isSpanComplete(span: ErrorSpan, protocol_error_categories: boolean): boolean {
    if (span.severity == null) return false
    // MQM categories require format "MainCategory/SubCategory" (e.g., "Accuracy/Mistranslation")
    if (protocol_error_categories && (span.category == null || !span.category.includes("/"))) return false
    return true
}

// Validation types for tutorial/attention checks
export type ValidationErrorSpan = { 
    start_i?: number | [number, number],  // exact value or range [min, max]
    end_i?: number | [number, number],    // exact value or range [min, max]
    severity?: string 
}
export type Validation = {
    warning?: string,  // Warning message to display on failure (attention check mode)
    score?: [number, number],  // [min, max] range for valid score
    score_greaterthan?: string,  // Model name that this score must be greater than
    error_spans?: Array<ValidationErrorSpan>,  // Expected error spans
    allow_skip?: boolean  // Show skip tutorial button
}
export type ValidationResult = { 
    valid: boolean, 
    failed_items: number[],  // indices of failed items
}

// MQM Error Categories
export const MQM_ERROR_CATEGORIES: { [key: string]: string[] } = {
    "": [],
    "Terminology": [
        "",
        "Inconsistent with terminology resource",
        "Inconsistent use of terminology",
        "Wrong term",
    ],
    "Accuracy": [
        "",
        "Mistranslation",
        "Overtranslation",
        "Undertranslation",
        "Addition",
        "Omission",
        "Do not translate",
        "Untranslated",
    ],
    "Linguistic conventions": [
        "",
        "Grammar",
        "Punctuation",
        "Spelling",
        "Unintelligible",
        "Character encoding",
        "Textual conventions",
    ],
    "Style": [
        "",
        "Organization style",
        "Third-party style",
        "Inconsistent with external reference",
        "Language register",
        "Awkward style",
        "Unidiomatic style",
        "Inconsistent style",
    ],
    "Locale convention": [
        "",
        "Number format",
        "Currency format",
        "Measurement format",
        "Time format",
        "Date format",
        "Address format",
        "Telephone format",
        "Shortcut key",
    ],
    "Audience appropriateness": [
        "",
        "Culture-specific reference",
        "Offensive",
    ],
    "Design and markup": [
        "",
        "Layout",
        "Markup tag",
        "Truncation/text expansion",
        "Missing text",
        "Link/cross-reference",
    ],
    "Other": [],
}

/**
 * Renders the progress bar for annotation tasks
 */
export function redrawProgress(current_i: number | null, progress: Array<boolean>, onItemClick?: (i: number) => void): void {
    let html = progress.map((v, i) => {
        if (i === current_i) {
            // Current item always gets the "current" highlight (larger indicator)
            return `<span class="progress_current" data-index="${i}">${i + 1}</span>`
        } else if (v) {
            return `<span class="progress_complete" data-index="${i}">${i + 1}</span>`
        } else {
            return `<span class="progress_incomplete" data-index="${i}">${i + 1}</span>`
        }
    }).join("")
    $("#progress").html(html)

    // Attach click handlers if callback is provided
    if (onItemClick) {
        $("#progress span").on("click", function() {
            const index = parseInt($(this).data("index"))
            onItemClick(index)
        })
    }
}

/**
 * Creates the span toolbox for error annotation
 */
export function createSpanToolbox(
    protocol_error_categories: boolean,
    error_span: ErrorSpan,
    tgt_chars_objs: Array<CharData>,
    left_i: number,
    right_i: number,
    onDelete: () => void,
    frozenMode: boolean = false
): JQuery<HTMLElement> {
    let toolbox = $(`
    <div class='span_toolbox_parent'>
    <div class='span_toolbox'>
      <div class="span_toolbox_esa" style="display: inline-block; width: 70px; padding-right: 5px;">
        <input type="button" class="error_delete" style="border-radius: 8px;" value="Remove">
        <input type="button" class="error_neutral" style="margin-top: 3px;" value="Neutral">
        <input type="button" class="error_minor" style="margin-top: 3px;" value="Minor">
        <input type="button" class="error_major" style="margin-top: 3px;" value="Major">
      </div>
      <div class="span_toolbox_mqm" style="display: inline-block; width: 140px; vertical-align: top;">
        <select style="height: 2em; width: 100%;"></select><br>
        <select style="height: 2em; width: 100%; margin-top: 3px;" disabled></select>
      </div>
    </div>
    </div>
    `)
    
    for (let category1 of Object.keys(MQM_ERROR_CATEGORIES)) {
        toolbox.find("select").eq(0).append(`<option value="${category1}">${category1}</option>`)
    }
    
    // select one category handler
    toolbox.find("select").eq(0).on("change", function () {
        if (frozenMode) return
        let cat1 = (<HTMLSelectElement>this).value
        error_span.category = cat1
        let subcat_select = toolbox.find("select").eq(1)
        subcat_select.empty()
        let subcats = MQM_ERROR_CATEGORIES[cat1]
        subcat_select.prop("disabled", false)
        for (let subcat of subcats) {
            subcat_select.append(`<option value="${subcat}">${subcat}</option>`)
        }
        if (cat1 == "") {
            subcat_select.prop("disabled", true)
            error_span.category = ""
        } else if (cat1 == "Other") {
            subcat_select.prop("disabled", true)
            error_span.category = "Other/Other"
        } else {
            error_span.category = `${cat1}`
        }
    })
    
    toolbox.find("select").eq(1).on("change", function () {
        if (frozenMode) return
        let cat1 = toolbox.find("select").eq(0).val() as string
        let cat2 = (<HTMLSelectElement>this).value
        // enforce both category and subcategory
        if (cat2 == "" && cat1 != "Other") {
            error_span.category = `${cat1}`
        } else {
            error_span.category = `${cat1}/${cat2}`
        }
    })
    
    if (!protocol_error_categories) {
        // only MQM has neutral severity
        toolbox.find(".error_neutral").remove()
        toolbox.find(".span_toolbox_mqm").remove()
        toolbox.find(".span_toolbox_esa").css("border-right", "")
        toolbox.find(".span_toolbox_esa").css("margin-right", "-5px")
    }
    
    // handle delete button
    toolbox.find(".error_delete").on("click", () => {
        if (frozenMode) return
        toolbox.remove()
        for (let j = left_i; j <= right_i; j++) {
            $(tgt_chars_objs[j].el).removeClass("error_unknown")
            $(tgt_chars_objs[j].el).removeClass("error_neutral")
            $(tgt_chars_objs[j].el).removeClass("error_minor")
            $(tgt_chars_objs[j].el).removeClass("error_major")
            tgt_chars_objs[j].toolbox = null
            tgt_chars_objs[j].error_span = null
        }
        onDelete()
    })
    
    // handle severity buttons
    toolbox.find(".error_neutral").on("click", () => {
        if (frozenMode) return
        for (let j = left_i; j <= right_i; j++) {
            $(tgt_chars_objs[j].el).removeClass("error_unknown")
            $(tgt_chars_objs[j].el).removeClass("error_minor")
            $(tgt_chars_objs[j].el).removeClass("error_major")
            $(tgt_chars_objs[j].el).addClass("error_neutral")
        }
        error_span.severity = "neutral"
    })
    
    toolbox.find(".error_minor").on("click", () => {
        if (frozenMode) return
        for (let j = left_i; j <= right_i; j++) {
            $(tgt_chars_objs[j].el).removeClass("error_unknown")
            $(tgt_chars_objs[j].el).removeClass("error_neutral")
            $(tgt_chars_objs[j].el).removeClass("error_major")
            $(tgt_chars_objs[j].el).addClass("error_minor")
        }
        error_span.severity = "minor"
    })
    
    toolbox.find(".error_major").on("click", () => {
        if (frozenMode) return
        for (let j = left_i; j <= right_i; j++) {
            $(tgt_chars_objs[j].el).removeClass("error_unknown")
            $(tgt_chars_objs[j].el).removeClass("error_neutral")
            $(tgt_chars_objs[j].el).removeClass("error_minor")
            $(tgt_chars_objs[j].el).addClass("error_major")
        }
        error_span.severity = "major"
    })
    
    // Restore category from error_span if it exists (for previously saved annotations)
    if (protocol_error_categories && error_span.category && error_span.category.includes("/")) {
        const [cat1, cat2] = error_span.category.split("/")
        const cat1_select = toolbox.find("select").eq(0)
        const cat2_select = toolbox.find("select").eq(1)
        
        // Set the first dropdown
        cat1_select.val(cat1)
        
        // Populate and set the second dropdown
        cat2_select.empty()
        const subcats = MQM_ERROR_CATEGORIES[cat1]
        if (subcats) {
            cat2_select.prop("disabled", false)
            for (let subcat of subcats) {
                cat2_select.append(`<option value="${subcat}">${subcat}</option>`)
            }
            cat2_select.val(cat2)
        }
    } else if (protocol_error_categories && error_span.category && error_span.category !== "") {
        // Handle case where only category is set (no subcategory yet)
        const cat1_select = toolbox.find("select").eq(0)
        cat1_select.val(error_span.category)
        
        // Populate the second dropdown but don't select anything yet
        const cat2_select = toolbox.find("select").eq(1)
        cat2_select.empty()
        const subcats = MQM_ERROR_CATEGORIES[error_span.category]
        if (subcats && error_span.category !== "Other") {
            cat2_select.prop("disabled", false)
            for (let subcat of subcats) {
                cat2_select.append(`<option value="${subcat}">${subcat}</option>`)
            }
        }
    }

    // In frozen mode, disable all modification controls
    if (frozenMode) {
        toolbox.find(".error_delete").prop("disabled", true)
        toolbox.find(".error_neutral").prop("disabled", true)
        toolbox.find(".error_minor").prop("disabled", true)
        toolbox.find(".error_major").prop("disabled", true)
        toolbox.find("select").prop("disabled", true)
    }
    
    return toolbox
}

/**
 * Updates toolbox position based on character element position
 */
export function updateToolboxPosition(toolbox: JQuery<HTMLElement>, charEl: JQuery<HTMLElement>): void {
    const position = charEl.position();
    if (!position) return;
    
    const toolboxHeight = toolbox.innerHeight() || 0;
    const toolboxWidth = toolbox.innerWidth() || 0;
    const windowWidth = $(window).width() || 900;
    
    let topPosition = position.top - toolboxHeight;
    let leftPosition = position.left;
    // make sure it's not getting out of screen
    leftPosition = Math.min(leftPosition, Math.max(windowWidth, 900) - toolboxWidth + 10);

    toolbox.css({
        top: topPosition,
        left: leftPosition - 25,
    });
}

/**
 * Check if a value is within a specified range
 */
function isInRange(value: number, range: number | [number, number]): boolean {
    if (Array.isArray(range)) {
        return value >= range[0] && value <= range[1];
    }
    return value === range;
}

/**
 * Check if a user error span matches a validation error span requirement
 */
function spanMatches(userSpan: ErrorSpan, validationSpan: ValidationErrorSpan): boolean {
    // Check start_i if specified
    if (validationSpan.start_i !== undefined) {
        if (!isInRange(userSpan.start_i, validationSpan.start_i)) {
            return false;
        }
    }
    // Check end_i if specified
    if (validationSpan.end_i !== undefined) {
        if (!isInRange(userSpan.end_i, validationSpan.end_i)) {
            return false;
        }
    }
    // Check severity if specified
    if (validationSpan.severity !== undefined) {
        if (userSpan.severity !== validationSpan.severity) {
            return false;
        }
    }
    return true;
}

/**
 * Validate a response dictionary with score comparison support
 * @param responses - Record of responses for all models
 * @param validations - Record of validation rules for all models
 * @param model - Model name being validated
 * @returns true if validation passes, false otherwise
 */
export function validateResponse(
    responses: Record<string, Response>,
    validations: Record<string, Validation>,
    model: string
): boolean {
    const response = responses[model];
    const validation = validations[model];
    
    if (!validation) {
        return true;
    }

    // Validate score range if specified
    if (validation.score !== undefined) {
        const [minScore, maxScore] = validation.score;
        if (response.score === null || response.score < minScore || response.score > maxScore) {
            return false
        }
    }
    
    // Validate error spans if specified
    if (validation.error_spans !== undefined && validation.error_spans.length > 0) {
        // Each expected span must be matched by at least one user span
        for (const expectedSpan of validation.error_spans) {
            const matched = response.error_spans.some(userSpan => spanMatches(userSpan, expectedSpan));
            if (!matched) {
                return false
            }
        }
    }

    // Validate score_greaterthan condition if specified
    if (validation.score_greaterthan !== undefined) {
        const otherModel = validation.score_greaterthan as string;
        
        // Validate the other model exists in responses
        if (!responses[otherModel]) {
            console.error(`Invalid score_greaterthan model: ${otherModel}`);
            return false;
        }
        
        const otherScore = responses[otherModel].score;
        // Both scores must be set (not null) to perform comparison
        // Null scores indicate the user hasn't provided a score yet
        if (response.score === null || otherScore === null) {
            return false;
        }
        
        // Verify this model's score is strictly greater than the other
        if (response.score <= otherScore) {
            return false;
        }
    }

    return true;
}

/**
 * Check if any validation has allow_skip enabled
 * Handles both Record validations and single Validation objects
 */
export function hasAllowSkip(validations: (Validation | Record<string, Validation> | undefined)[]): boolean {
    for (const v of validations) {
        if (!v) continue;
        if (typeof v === 'object' && !Array.isArray(v)) {
            // Check if it's a single Validation object (has allow_skip property directly)
            if ('allow_skip' in v && v.allow_skip === true) {
                return true;
            }
            // Otherwise treat as Record and check nested validations
            if (!('allow_skip' in v) && !('warning' in v) && !('score' in v)) {
                // It's a Record<string, Validation>
                if (Object.values(v).some(vv => vv?.allow_skip === true)) return true;
            }
        }
    }
    return false;
}

// Shared type for goodbye response
export type DataGoodbye = {
    status: string,
    progress: Array<boolean>,
    time: number,
    token: string,
    instructions_goodbye?: string,
}

// Shared protocol info type
export type ProtocolInfo = {
    protocol: "DA" | "ESA" | "MQM",
    item_i: number,
    sliders?: string[],  // Optional custom slider names
    instructions?: string,
}

/**
 * Display goodbye screen when all annotations are done
 */
export function displayGoodbyeScreen(response: DataGoodbye, navigate_to_item: (i: number) => void): void {
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
    redrawProgress(null, response.progress, navigate_to_item)
    $("#time").text(`Time: ${Math.round(response.time / 60)}m`)
    $("#button_next").prop("disabled", true)
    $("#button_next").val("Next 💯")
}

/**
 * Check if content is a media tag (audio, video, img, iframe)
 */
export function isMediaContent(content: string): boolean {
    return content.startsWith("<audio ") || 
           content.startsWith("<video ") || 
           content.startsWith("<img ") || 
           content.startsWith("<iframe ")
}

/**
 * Detect text direction based on Unicode Bidirectional Algorithm
 * Returns 'rtl' if the first strong directional character is RTL, otherwise 'ltr'
 */
export function detectTextDirection(text: string): 'rtl' | 'ltr' {
    // RTL character ranges: Hebrew, Arabic, Syriac, Thaana, N'Ko, Samaritan
    const rtlRegex = /[\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFC]/
    // LTR character ranges: Latin, Cyrillic, Greek
    const ltrRegex = /[A-Za-z\u00C0-\u024F\u0400-\u04FF\u0370-\u03FF]/
    
    // Check first strong directional character
    for (const char of text) {
        if (rtlRegex.test(char)) {
            return 'rtl'
        }
        if (ltrRegex.test(char)) {
            return 'ltr'
        }
    }
    
    return 'ltr'
}

/**
 * Convert text content to character spans with line break handling
 */
export function contentToCharSpans(content: string, className: string): string {
    return content.split("").map(c => c == "\n" ? "<br>" : `<span class="${className}">${c}</span>`).join("")
}

/**
 * Compute word boundaries for each character index in the content (list of characters).
 * Returns an array where each element contains [word_start, word_end] for that character index.
 * Word boundaries are defined by non-alphanumeric characters.
 */
const is_alphanum = /^\p{L}|\p{N}$/u
export function computeWordBoundaries(content: string[]): Array<[number, number]> {
    const boundaries: Array<[number, number]> = []
    
    for (let i = 0; i < content.length; i++) {
        // non-alphanumeric characters are their own words
        if (!is_alphanum.test(content[i])) {
            boundaries.push([i, i])
        } else {
            // Find the end of this word that's all alphanumeric
            let word_start = i
            while (i < content.length - 1 && is_alphanum.test(content[i+1])) {
                i++;
            }
            for(let j = word_start; j <= i; j++) {
                boundaries.push([word_start, i])
            }
        }
    }
    
    return boundaries
}
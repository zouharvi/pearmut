"""Default instructions for different annotation protocols."""

# Default instructions for each protocol
# These are used when no custom instructions are provided
PROTOCOL_INSTRUCTIONS = {
    "DA": """
        <ul>
          <li>Score each translation using the slider based on meaning preservation and quality.
            <strong>Important:</strong> The relative order of scores matters; ensure better translations have higher
            scores than worse ones.
            <ul>
              <li>0: <strong>Nonsense</strong>: most information is lost.</li>
              <li>33%: <strong>Broken</strong>: major gaps and narrative issues.</li>
              <li>66%: <strong>Middling</strong>: minor issues with grammar or consistency.</li>
              <li>100%: <strong>Perfect</strong>: meaning and grammar align completely with the source.</li>
            </ul>
          </li>
        </ul>
    """,
    "ESA": """
        <ul>
          <li>Error spans:
            <ul>
              <li><strong>Click</strong> on the start of an error, then <strong>click</strong> on the end to mark an
                error span.</li>
              <li><strong>Hover</strong> over an existing highlight to change error severity (minor/major) or remove it.
              </li>
            </ul>
            Error severity:
            <ul>
              <li><span class="instruction_sev" id="instruction_sev_minor">Minor:</span> Style, grammar, or word choice
                could be better.</li>
              <li><span class="instruction_sev" id="instruction_sev_major">Major:</span> Meaning is significantly
                changed or is hard to understand.</li>
            </ul>
            <strong>Tip</strong>: Mark the general area of the error (doesn't need to be exact). Use separate highlights
            for different errors.
            Use <code>[missing]</code> at the end of a sentence for omitted content.<br>
          </li>
          <li>Score each translation using the slider based on meaning preservation and quality.
            <strong>Important:</strong> The relative order of scores matters; ensure better translations have higher
            scores than worse ones.
            <ul>
              <li>0: <strong>Nonsense</strong>: most information is lost.</li>
              <li>33%: <strong>Broken</strong>: major gaps and narrative issues.</li>
              <li>66%: <strong>Middling</strong>: minor issues with grammar or consistency.</li>
              <li>100%: <strong>Perfect</strong>: meaning and grammar align completely with the source.</li>
            </ul>
          </li>
        </ul>
    """,
    "MQM": """
        <ul>
          <li>Error spans:
            <ul>
              <li><strong>Click</strong> on the start of an error, then <strong>click</strong> on the end to mark an
                error span.</li>
              <li><strong>Hover</strong> over an existing highlight to change error severity (minor/major) or remove it.
              </li>
            </ul>
            Error severity:
            <ul>
              <li><span class="instruction_sev" id="instruction_sev_minor">Minor:</span> Style, grammar, or word choice
                could be better.</li>
              <li><span class="instruction_sev" id="instruction_sev_major">Major:</span> Meaning is significantly
                changed or is hard to understand.</li>
            </ul>
            <strong>Tip</strong>: Mark the general area of the error (doesn't need to be exact). Use separate highlights
            for different errors.
            Use <code>[missing]</code> at the end of a sentence for omitted content.<br>
          </li>
          <li>Score each translation using the slider based on meaning preservation and quality.
            <strong>Important:</strong> The relative order of scores matters; ensure better translations have higher
            scores than worse ones.
            <ul>
              <li>0: <strong>Nonsense</strong>: most information is lost.</li>
              <li>33%: <strong>Broken</strong>: major gaps and narrative issues.</li>
              <li>66%: <strong>Middling</strong>: minor issues with grammar or consistency.</li>
              <li>100%: <strong>Perfect</strong>: meaning and grammar align completely with the source.</li>
            </ul>
          </li>
          <li>
            Error types:
            After highlighting an error fragment, you will be asked to select the specific error type (main category and
            subcategory).
            If you are unsure about which errors fall under which categories, please consult the <a
              href="https://themqm.org/the-mqm-typology/"
              style="font-weight: bold; text-decoration: none; color: black;">typology
              definitions</a>.
          </li>
        </ul>
    """,
}

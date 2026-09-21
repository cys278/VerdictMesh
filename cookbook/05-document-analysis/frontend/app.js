const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const leftPanel = document.getElementById('left-panel');
const rightPanel = document.getElementById('right-panel');
const controls = document.getElementById('controls');
const documentContent = document.getElementById('document-content');
const dispatchBtn = document.getElementById('dispatch-btn');
const feed = document.getElementById('feed');
const legendContainer = document.getElementById('agent-legend');
const tooltip = document.getElementById('insight-tooltip');

// Escape untrusted text before inserting it with innerHTML.
const escapeHtml = value => String(value ?? '').replace(
    /[&<>"']/g,
    character => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    })[character]
);

// Only allow valid hexadecimal colors in inline styles.
const safeColor = value => {
    const color = String(value ?? '');
    return /^#[0-9a-fA-F]{6}$/.test(color) ? color : '#64748b';
};

// --- State Management ---
let globalSentenceState = {};
let activeAgentFilters = {};
let tooltipTimeout;
let documentId = null;

const HOVER_DELAY_MS = 800;
const CURSOR_OFFSET = 5;

// --- Helper: Convert Hex to RGB ---
const hexToRgb = hex => {
    const safeHex = safeColor(hex);

    const r = parseInt(safeHex.slice(1, 3), 16);
    const g = parseInt(safeHex.slice(3, 5), 16);
    const b = parseInt(safeHex.slice(5, 7), 16);

    return `${r}, ${g}, ${b}`;
};

// --- Drag and Drop Logic ---
dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        fileInput.click();
    }
});

dropZone.addEventListener('dragover', event => {
    event.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', event => {
    event.preventDefault();
    dropZone.classList.remove('dragover');

    if (event.dataTransfer.files.length) {
        handleFileUpload(event.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', event => {
    if (event.target.files.length) {
        handleFileUpload(event.target.files[0]);
    }
});

// --- API: Upload and Parse ---
async function handleFileUpload(file) {
    dropZone.innerHTML =
        "<p class='drop-subtitle'>Uploading and parsing document...</p>";

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok || data.status !== 'success') {
            throw new Error(data.message || 'The document could not be uploaded.');
        }

        documentId = data.document_id;

        if (!documentId) {
            throw new Error('The backend did not return a document ID.');
        }

        dropZone.style.display = 'none';
        leftPanel.classList.add('active');
        rightPanel.classList.add('active');
        controls.style.display = 'block';

        /*
         * Sentence HTML comes from the backend PDF parser.
         * The parser must escape the original PDF text before adding
         * its own formatting tags.
         */
        documentContent.innerHTML = data.sentences.map(paragraph => {
            const paragraphText = paragraph.sentences.map(sentence =>
                `<span class="document-sentence" id="sent-${escapeHtml(sentence.sentence_id)}">${sentence.sentence} </span>`
            ).join('');

            return `<p>${paragraphText}</p>`;
        }).join('');
    } catch (error) {
        documentId = null;
        dropZone.innerHTML =
            '<p class="drop-subtitle" style="color: #d93025;">' +
            'Upload failed. Make sure the backend is running and the file is a valid PDF.' +
            '</p>';

        console.error('Document upload failed:', error);
    }
}

// --- API: Trigger Multi-Agent Analysis via SSE ---
dispatchBtn.addEventListener('click', () => {
    if (!documentId) {
        addFeedStatus('Upload a document before starting the audit.');
        dispatchBtn.disabled = false;
        dispatchBtn.innerText = 'Dispatch Parallel Agents';
        return;
    }

    dispatchBtn.disabled = true;
    dispatchBtn.innerText = 'Analyzing concurrently...';
    feed.innerHTML = '';

    legendContainer.style.display = 'none';
    legendContainer.innerHTML =
        '<div style="font-weight: 600; margin-bottom: 4px;">Active Perspectives</div>';

    globalSentenceState = {};
    activeAgentFilters = {};

    const eventSource = new EventSource(
        `/api/analyze?document_id=${encodeURIComponent(documentId)}`
    );

    eventSource.onmessage = event => {
        try {
            const payload = JSON.parse(event.data);

            if (
                payload.status === 'engine_started' ||
                payload.status === 'aggregator_started'
            ) {
                addFeedStatus(payload.message);
            } else if (payload.status === 'agent_report') {
                const agentData = payload.data;

                addAgentCard(agentData);
                registerAgentInLegend(agentData.agent, agentData.color);

                processAgentHighlights(
                    agentData.agent,
                    agentData.color,
                    agentData.insight,
                    agentData.selected_sentence_ids
                );
            } else if (payload.status === 'conflict_report') {
                addConflictReport(payload.data);
            } else if (payload.status === 'error') {
                eventSource.close();
                dispatchBtn.innerText = 'Dispatch Parallel Agents';
                dispatchBtn.disabled = false;
                addFeedStatus(`Audit failed: ${payload.message}`);
            } else if (payload.status === 'complete') {
                eventSource.close();
                dispatchBtn.innerText = 'Audit Complete';
                addFeedStatus('Workflow Terminated Successfully.');
                legendContainer.style.display = 'flex';
            }
        } catch (error) {
            console.error('Invalid analysis event:', error);
        }
    };

    eventSource.onerror = error => {
        console.error('SSE Error:', error);
        eventSource.close();

        dispatchBtn.innerText = 'Dispatch Parallel Agents';
        dispatchBtn.disabled = false;

        addFeedStatus(
            'The analysis connection stopped. Check the backend terminal for details.'
        );
    };
});

// --- UI Rendering Helpers ---
function addFeedStatus(message) {
    const element = document.createElement('div');
    element.className = 'status-text';
    element.innerText = `> ${String(message ?? '')}`;

    feed.appendChild(element);
    rightPanel.scrollTop = rightPanel.scrollHeight;
}

function addAgentCard(data) {
    const element = document.createElement('div');
    const color = safeColor(data.color);

    element.className = 'card agent-card';
    element.style.borderLeftColor = color;

    element.innerHTML = `
        <div
            class="card-title"
            style="color: ${color}; filter: brightness(0.7);"
        >
            ${escapeHtml(data.agent)}
        </div>
        <p style="font-size: 0.95rem;">
            ${escapeHtml(data.insight)}
        </p>
    `;

    feed.appendChild(element);
    rightPanel.scrollTop = rightPanel.scrollHeight;
}

function addConflictReport(consensus) {
    const element = document.createElement('div');
    element.className = 'card conflict-card';

    let reportHtml = `
        <div class="card-title" style="color: #d93025;">
            Chief Justice Report
        </div>
    `;

    if (
        consensus?.has_conflicts &&
        Array.isArray(consensus.conflicts) &&
        consensus.conflicts.length
    ) {
        reportHtml += `
            <p style="font-weight: 600; margin-bottom: 8px;">
                ${escapeHtml(consensus.summary)}
            </p>
        `;

        consensus.conflicts.forEach(conflict => {
            const involvedAgents = Array.isArray(conflict.involved_agents)
                ? conflict.involved_agents.join(', ')
                : '';

            reportHtml += `
                <div
                    style="
                        background: rgba(255, 255, 255, 0.7);
                        padding: 8px;
                        border-radius: 4px;
                        margin-top: 8px;
                        border-left: 2px solid #d93025;
                    "
                >
                    <strong>[${escapeHtml(conflict.severity)}]</strong>
                    ${escapeHtml(conflict.description)}
                    <br>
                    <small style="color: var(--text-secondary);">
                        Involved: ${escapeHtml(involvedAgents)}
                    </small>
                </div>
            `;
        });
    } else {
        reportHtml += `
            <p>
                All executive perspectives are aligned.
                No critical cross-domain conflicts detected.
            </p>
        `;
    }

    element.innerHTML = reportHtml;
    feed.appendChild(element);
    rightPanel.scrollTop = rightPanel.scrollHeight;
}

// --- Dynamic Highlighting and Legend Logic ---
function registerAgentInLegend(agentName, color) {
    if (activeAgentFilters[agentName] !== undefined) {
        return;
    }

    activeAgentFilters[agentName] = true;

    const safeAgentName = escapeHtml(agentName);
    const agentColor = safeColor(color);
    const label = document.createElement('label');

    label.className = 'legend-item';
    label.innerHTML = `
        <input type="checkbox" checked value="${safeAgentName}">
        <span
            class="legend-color-box"
            style="background-color: ${agentColor};"
        ></span>
        ${safeAgentName}
    `;

    label.querySelector('input').addEventListener('change', event => {
        activeAgentFilters[agentName] = event.target.checked;
        recalculateAllHighlights();
    });

    legendContainer.appendChild(label);
}

function processAgentHighlights(agentName, color, insight, sentenceIds) {
    if (!Array.isArray(sentenceIds)) {
        return;
    }

    sentenceIds.forEach(id => {
        if (!globalSentenceState[id]) {
            globalSentenceState[id] = {};
        }

        globalSentenceState[id][agentName] = {
            color: safeColor(color),
            insight
        };
    });

    recalculateAllHighlights();
}

function recalculateAllHighlights() {
    for (
        const [sentenceId, agentsDictionary]
        of Object.entries(globalSentenceState)
    ) {
        const sentenceElement = document.getElementById(
            `sent-${sentenceId}`
        );

        if (!sentenceElement) {
            continue;
        }

        const activeColors = [];

        for (
            const [agentName, data]
            of Object.entries(agentsDictionary)
        ) {
            if (activeAgentFilters[agentName]) {
                activeColors.push(safeColor(data.color));
            }
        }

        if (activeColors.length === 0) {
            sentenceElement.style.background = 'transparent';
            sentenceElement.style.borderBottomColor = 'transparent';
            sentenceElement.classList.remove('has-highlight');
        } else if (activeColors.length === 1) {
            const color = activeColors[0];

            sentenceElement.classList.add('has-highlight');
            sentenceElement.style.background =
                `rgba(${hexToRgb(color)}, 0.3)`;
            sentenceElement.style.borderBottomColor = color;
        } else {
            const stripeWidth = 10;
            const gradientStops = [];

            activeColors.forEach((color, index) => {
                const rgba = `rgba(${hexToRgb(color)}, 0.4)`;
                const start = index * stripeWidth;
                const end = (index + 1) * stripeWidth;

                gradientStops.push(
                    `${rgba} ${start}px, ${rgba} ${end}px`
                );
            });

            const totalWidth = activeColors.length * stripeWidth;

            sentenceElement.classList.add('has-highlight');
            sentenceElement.style.background =
                `repeating-linear-gradient(
                    45deg,
                    ${gradientStops.join(', ')},
                    ${gradientStops[0]} ${totalWidth}px
                )`;

            sentenceElement.style.borderBottomColor = '#444746';
        }
    }
}

// --- Tooltip Hover Logic ---
documentContent.addEventListener('mouseover', event => {
    const sentenceElement = event.target.closest('.document-sentence');

    if (!sentenceElement) {
        return;
    }

    const sentenceId = sentenceElement.id.replace('sent-', '');
    const agentsDictionary = globalSentenceState[sentenceId];

    let activeAgentsHtml = '';

    if (agentsDictionary) {
        for (
            const [agentName, data]
            of Object.entries(agentsDictionary)
        ) {
            if (activeAgentFilters[agentName]) {
                activeAgentsHtml += `
                    <div class="tooltip-agent-block">
                        <div
                            class="tooltip-agent-name"
                            style="
                                color: ${safeColor(data.color)};
                                filter: brightness(0.7);
                            "
                        >
                            ${escapeHtml(agentName)}
                        </div>
                        <div class="tooltip-insight-text">
                            ${escapeHtml(data.insight)}
                        </div>
                    </div>
                `;
            }
        }
    }

    if (!activeAgentsHtml) {
        return;
    }

    clearTimeout(tooltipTimeout);
    tooltip.innerHTML = activeAgentsHtml;

    tooltip.style.visibility = 'hidden';
    tooltip.style.opacity = '0';
    tooltip.classList.add('visible');

    const tooltipRectangle = tooltip.getBoundingClientRect();

    let leftPosition = event.pageX + CURSOR_OFFSET;
    let topPosition = event.pageY + CURSOR_OFFSET;

    if (
        event.clientX +
        CURSOR_OFFSET +
        tooltipRectangle.width >
        window.innerWidth
    ) {
        leftPosition =
            event.pageX -
            tooltipRectangle.width -
            CURSOR_OFFSET;
    }

    if (
        event.clientY +
        CURSOR_OFFSET +
        tooltipRectangle.height >
        window.innerHeight
    ) {
        topPosition =
            event.pageY -
            tooltipRectangle.height -
            CURSOR_OFFSET;
    }

    tooltip.style.left = `${Math.max(0, leftPosition)}px`;
    tooltip.style.top = `${Math.max(0, topPosition)}px`;
    tooltip.style.visibility = '';
    tooltip.style.opacity = '';
});

documentContent.addEventListener('mouseout', event => {
    const sentenceElement = event.target.closest('.document-sentence');

    if (sentenceElement) {
        tooltipTimeout = setTimeout(() => {
            tooltip.classList.remove('visible');
        }, HOVER_DELAY_MS);
    }
});

tooltip.addEventListener('mouseenter', () => {
    clearTimeout(tooltipTimeout);
});

tooltip.addEventListener('mouseleave', () => {
    tooltipTimeout = setTimeout(() => {
        tooltip.classList.remove('visible');
    }, HOVER_DELAY_MS);
});
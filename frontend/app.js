// Global variables
let currentDocumentId = null;
let currentCardId = null;
let currentCardData = null;  // Store full card data including type
const API_BASE_URL = "http://127.0.0.1:8000";

/**
 * Switch between tabs
 */
function switchTab(tabName) {
    console.log('Switching to tab:', tabName);
    
    // Get all tab panels and buttons
    const allPanels = document.querySelectorAll('.tab-panel');
    const allButtons = document.querySelectorAll('.tab-button');
    
    // Hide all panels
    allPanels.forEach(panel => {
        panel.classList.remove('active');
        panel.style.display = 'none';
    });
    
    // Deactivate all buttons
    allButtons.forEach(button => {
        button.classList.remove('active');
    });
    
    // Show the selected panel
    const targetPanel = document.getElementById(tabName + '-tab');
    if (targetPanel) {
        targetPanel.classList.add('active');
        targetPanel.style.display = 'block';
        console.log('Activated panel:', tabName + '-tab');
    } else {
        console.error('Panel not found:', tabName + '-tab');
    }
    
    // Activate the corresponding button
    allButtons.forEach(button => {
        const onclick = button.getAttribute('onclick');
        if (onclick && onclick.includes("'" + tabName + "'")) {
            button.classList.add('active');
        }
    });
    
    // Auto-load content for browse tab
    if (tabName === 'browse') {
        loadAllCards();
    }
}

/**
 * Upload a PDF file to the backend
 */
async function uploadPdf() {
    const fileInput = document.getElementById("pdfFile");
    const statusElement = document.getElementById("uploadStatus");
    
    // Clear previous status
    statusElement.textContent = "";
    statusElement.className = "status-message";
    
    // Validate file selection
    if (!fileInput.files || fileInput.files.length === 0) {
        statusElement.textContent = "Please select a PDF file first.";
        statusElement.classList.add("error");
        return;
    }
    
    const file = fileInput.files[0];
    
    // Validate file type
    if (!file.name.toLowerCase().endsWith(".pdf")) {
        statusElement.textContent = "Please select a valid PDF file.";
        statusElement.classList.add("error");
        return;
    }
    
    // Show loading status
    statusElement.textContent = "Uploading and processing PDF...";
    statusElement.classList.add("info");
    
    try {
        // Create form data
        const formData = new FormData();
        formData.append("file", file);
        
        // Upload the file
        const response = await fetch(`${API_BASE_URL}/api/upload/pdf`, {
            method: "POST",
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Upload failed: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Store document ID globally
        currentDocumentId = data.document_id;
        
        // Update the document ID input in the Progress section
        document.getElementById("docId").value = data.document_id;
        
        // Update study mode indicator
        const modeIndicator = document.getElementById("studyMode");
        modeIndicator.textContent = `📖 Ready to study: ${data.title}`;
        modeIndicator.className = "study-mode-indicator success";
        
        // Show success message
        statusElement.textContent = `✓ Uploaded "${data.title}". Document ID: ${data.document_id}. Cards created: ${data.cards_created}.`;
        statusElement.classList.remove("info");
        statusElement.classList.add("success");
        
        // Clear file input
        fileInput.value = "";
        
    } catch (error) {
        console.error("Upload error:", error);
        statusElement.textContent = `Error uploading PDF: ${error.message}`;
        statusElement.classList.remove("info");
        statusElement.classList.add("error");
    }
}

/**
 * Load the next card for studying with adaptive selection
 */
async function loadNextCard() {
    const cardFrontElement = document.getElementById("cardFront");
    const studyAnswerEl = document.getElementById("studyAnswer");
    const typeBadgeEl = document.getElementById("studyTypeBadge");
    const difficultyEl = document.getElementById("studyDifficulty");
    const feedbackElement = document.getElementById("feedback");
    
    // Clear all answer sections
    clearAnswerSections();
    
    // Clear previous state
    feedbackElement.textContent = "";
    feedbackElement.className = "feedback";
    currentCardId = null;
    currentCardData = null;
    if (studyAnswerEl) { studyAnswerEl.style.display = 'none'; studyAnswerEl.textContent = ''; }
    if (typeBadgeEl) { typeBadgeEl.style.display = 'none'; typeBadgeEl.textContent = ''; typeBadgeEl.className = 'card-type-badge'; }
    if (difficultyEl) { difficultyEl.style.display = 'none'; difficultyEl.textContent = ''; difficultyEl.className = 'card-difficulty'; }
    
    // Show loading state
    cardFrontElement.textContent = "Loading next card...";
    
    try {
        // Use adaptive card selection if document is selected
        let url = `${API_BASE_URL}/api/session/next-card`;
        if (currentDocumentId) {
            url = `${API_BASE_URL}/api/session/next-card-adaptive?document_id=${encodeURIComponent(currentDocumentId)}`;
        }
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`Failed to load card: ${response.statusText}`);
        }
        
        const card = await response.json();
        
        // Check if no cards available
        if (!card || card === null) {
            cardFrontElement.textContent = "No cards available or all done for now.";
            currentCardId = null;
            return;
        }
        
        // Store card data
        currentCardId = card.id;
        currentCardData = card;
        const type = (card.type || '').toLowerCase();
        
        // Show type badge
        if (typeBadgeEl && type) {
            typeBadgeEl.textContent = type;
            typeBadgeEl.className = `card-type-badge card-type-${type}`;
            typeBadgeEl.style.display = 'inline-block';
        }
        
        // Render card based on type
        renderCardByType(card, type, cardFrontElement);
        
    } catch (error) {
        console.error("Error loading card:", error);
        cardFrontElement.textContent = `Error loading card: ${error.message}`;
    }
}

/**
 * Clear all answer input sections
 */
function clearAnswerSections() {
    const mcqOptions = document.getElementById("mcqOptions");
    const textAnswerSection = document.getElementById("textAnswerSection");
    const selfGradeSection = document.getElementById("selfGradeSection");
    const answerInput = document.getElementById("answerInput");
    const revealButton = document.getElementById("revealButton");
    
    if (mcqOptions) {
        mcqOptions.style.display = 'none';
        mcqOptions.innerHTML = '';
    }
    if (textAnswerSection) {
        textAnswerSection.style.display = 'none';
    }
    if (answerInput) {
        answerInput.value = '';
    }
    if (selfGradeSection) {
        selfGradeSection.style.display = 'none';
    }
    if (revealButton) {
        revealButton.style.display = 'inline-block';
    }
}

/**
 * Render card based on its type
 */
function renderCardByType(card, type, cardFrontElement) {
    const mcqOptions = document.getElementById("mcqOptions");
    const textAnswerSection = document.getElementById("textAnswerSection");
    const revealButton = document.getElementById("revealButton");
    
    if (type === 'mcq') {
        // MCQ: Parse options from front text and render as buttons
        const parts = card.front.split('\n');
        const optStart = parts.findIndex(l => l.trim().toLowerCase().startsWith('options:'));
        
        if (optStart !== -1) {
            const question = parts.slice(0, optStart).join('\n');
            cardFrontElement.textContent = question;
            
            const optionLines = parts.slice(optStart + 1).filter(Boolean);
            if (optionLines.length && mcqOptions) {
                mcqOptions.innerHTML = '';
                optionLines.forEach((line, index) => {
                    const cleanText = line.replace(/^\s*[A-Fa-f]\)\s*/, '');
                    const button = document.createElement('button');
                    button.className = 'mcq-option-button';
                    button.innerHTML = `<span class="option-label">${String.fromCharCode(65 + index)}</span>${cleanText}`;
                    button.onclick = () => submitMCQAnswer(index);
                    mcqOptions.appendChild(button);
                });
                mcqOptions.style.display = 'grid';
            }
        } else {
            cardFrontElement.textContent = card.front;
        }
        
        // Hide reveal button for MCQ
        if (revealButton) revealButton.style.display = 'none';
        
    } else if (type === 'cloze') {
        // Cloze: Show text input
        cardFrontElement.textContent = card.front;
        if (textAnswerSection) {
            textAnswerSection.style.display = 'block';
        }
        
    } else {
        // Definition/Application: Show question, reveal button, then self-grade
        cardFrontElement.textContent = card.front;
    }
}

function revealAnswer() {
    const studyAnswerEl = document.getElementById('studyAnswer');
    const selfGradeSection = document.getElementById('selfGradeSection');
    const revealButton = document.getElementById('revealButton');
    
    if (!currentCardData) return;
    
    // Show the answer
    if (studyAnswerEl) {
        studyAnswerEl.textContent = currentCardData.back || '';
        studyAnswerEl.style.display = 'block';
    }
    
    // Hide reveal button
    if (revealButton) {
        revealButton.style.display = 'none';
    }
    
    // Show self-grade buttons for definition/application/connection cards
    const type = (currentCardData.type || '').toLowerCase();
    if (type === 'definition' || type === 'application' || type === 'connection') {
        if (selfGradeSection) {
            selfGradeSection.style.display = 'block';
        }
    }
}

/**
 * Submit MCQ answer (button click)
 */
async function submitMCQAnswer(optionIndex) {
    await submitAnswerGeneric(optionIndex);
}

/**
 * Submit text answer (for cloze cards)
 */
async function submitAnswer() {
    const answerInput = document.getElementById("answerInput");
    const feedbackElement = document.getElementById("feedback");
    
    if (!currentCardId) {
        feedbackElement.textContent = "Please load a card first.";
        feedbackElement.classList.add("warning");
        return;
    }
    
    const userAnswer = answerInput.value.trim();
    if (!userAnswer) {
        feedbackElement.textContent = "Please enter an answer.";
        feedbackElement.classList.add("warning");
        return;
    }
    
    await submitAnswerGeneric(userAnswer);
}

/**
 * Submit self-grade score (for definition/application cards)
 */
async function submitSelfGrade(score) {
    await submitAnswerGeneric(score);
}

/**
 * Generic answer submission handler
 */
async function submitAnswerGeneric(userAnswer) {
    const feedbackElement = document.getElementById("feedback");
    
    // Clear previous feedback
    feedbackElement.textContent = "";
    feedbackElement.className = "feedback";
    
    if (!currentCardId) {
        feedbackElement.textContent = "No card loaded.";
        feedbackElement.classList.add("warning");
        return;
    }
    
    // Show loading state
    feedbackElement.textContent = "Grading your answer...";
    feedbackElement.classList.add("info");
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/session/answer`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                card_id: currentCardId,
                user_answer: userAnswer,
                latency_ms: 1000
            })
        });
        
        if (!response.ok) {
            throw new Error(`Failed to submit answer: ${response.statusText}`);
        }
        
        const result = await response.json();
        
        // Display feedback with score
        const scoreEmoji = result.score === 3 ? "🎉" : result.score === 2 ? "👍" : result.score === 1 ? "📝" : "❌";
        feedbackElement.textContent = `${scoreEmoji} Score: ${result.score}/3 - ${result.explanation}`;
        feedbackElement.className = "feedback";
        
        if (result.score >= 2) {
            feedbackElement.classList.add("success");
        } else if (result.score === 1) {
            feedbackElement.classList.add("warning");
        } else {
            feedbackElement.classList.add("error");
        }
        
    } catch (error) {
        console.error("Error submitting answer:", error);
        feedbackElement.textContent = `Error submitting answer: ${error.message}`;
        feedbackElement.classList.remove("info");
        feedbackElement.classList.add("error");
    }
}

/**
 * Study all documents (clear document filter)
 */
function studyAllDocuments() {
    currentDocumentId = null;
    const modeIndicator = document.getElementById("studyMode");
    modeIndicator.textContent = "📚 Studying all documents";
    modeIndicator.className = "study-mode-indicator info";
    
    // Clear the card display
    document.getElementById("cardFront").textContent = "Click 'Next Card' to study from all documents.";
    document.getElementById("answerInput").value = "";
    document.getElementById("feedback").textContent = "";
    document.getElementById("feedback").className = "feedback";
}

/**
 * Load and display all cards organized by document and topic
 */
async function loadAllCards() {
    const browseContent = document.getElementById("browseContent");
    
    // Show loading state
    browseContent.innerHTML = "<p class='info'>Loading all cards...</p>";
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/progress/browse`);
        
        if (!response.ok) {
            throw new Error(`Failed to load cards: ${response.statusText}`);
        }
        
        const data = await response.json();
        // cache raw data for client-side filtering
        window.__browseData = data;
        
        if (!data.documents || data.documents.length === 0) {
            browseContent.innerHTML = "<p class='info'>No cards found. Upload a PDF to get started!</p>";
            return;
        }
        
        // Populate filters and render using unified renderer
        populateBrowseFilters(data);
        const filtered = applyBrowseFilters(data);
        renderFilteredBrowse(filtered);
        
    } catch (error) {
        console.error("Error loading cards:", error);
        browseContent.innerHTML = `<p class='error'>Error loading cards: ${error.message}</p>`;
    }
}

function populateBrowseFilters(data) {
    const docSel = document.getElementById('filterDocument');
    const macroSel = document.getElementById('filterMacro');
    const microSel = document.getElementById('filterMicro');
    const typeSel = document.getElementById('filterType');
    const diffSel = document.getElementById('filterDifficulty');

    if (!docSel || !macroSel || !microSel || !typeSel || !diffSel) return;

    const docOptions = ['<option value="">All Documents</option>'];
    const isDemo = (title) => {
        const t = (title || '').toLowerCase();
        return t.includes('demo') || t.includes('sample') || t.includes('example');
    };

    data.documents.forEach(d => {
        const name = d.title || d.name;
        if (isDemo(name)) return; // skip demo/sample docs in filters
        docOptions.push(`<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`);
    });
    docSel.innerHTML = docOptions.join('');

    // Populate macros and micros (cascading)
    const macrosSet = new Set();
    const macroToMicros = new Map();
    data.documents.forEach(d => {
        const name = d.title || d.name;
        if (isDemo(name)) return;
        if (d.macros) {
            d.macros.forEach(m => {
                macrosSet.add(m.macro_topic_name);
                const list = macroToMicros.get(m.macro_topic_name) || new Set();
                m.micro_topics.forEach(mi => list.add(mi.micro_topic_name));
                macroToMicros.set(m.macro_topic_name, list);
            });
        } else if (d.topics) {
            // Legacy: derive macros from left part of "Macro - Micro"
            d.topics.forEach(t => {
                const parts = (t.name || '').split(' - ');
                const macro = parts[0] || 'Uncategorized';
                const micro = parts[1] || 'General';
                macrosSet.add(macro);
                const list = macroToMicros.get(macro) || new Set();
                list.add(micro);
                macroToMicros.set(macro, list);
            });
        }
    });
    const macroOptions = ['<option value="">All Macros</option>', ...Array.from(macrosSet).map(m => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`)];
    macroSel.innerHTML = macroOptions.join('');
    // Initialize micros for current macro selection
    const currentMacro = macroSel.value;
    const microOptions = ['<option value="">All Micros</option>'];
    if (currentMacro && macroToMicros.has(currentMacro)) {
        microOptions.push(...Array.from(macroToMicros.get(currentMacro)).map(mi => `<option value="${escapeHtml(mi)}">${escapeHtml(mi)}</option>`));
    } else {
        // Aggregate all micros
        const allMicros = new Set();
        for (const list of macroToMicros.values()) {
            list.forEach(v => allMicros.add(v));
        }
        microOptions.push(...Array.from(allMicros).map(mi => `<option value="${escapeHtml(mi)}">${escapeHtml(mi)}</option>`));
    }
    microSel.innerHTML = microOptions.join('');

    ['filterDocument','filterMacro','filterMicro','filterType','filterDifficulty'].forEach(id => {
        const el = document.getElementById(id);
        el.onchange = () => {
            // Rebuild micros when macro changes
            if (id === 'filterMacro') {
                const selectedMacro = macroSel.value;
                const microOptions = ['<option value="">All Micros</option>'];
                if (selectedMacro && macroToMicros.has(selectedMacro)) {
                    microOptions.push(...Array.from(macroToMicros.get(selectedMacro)).map(mi => `<option value="${escapeHtml(mi)}">${escapeHtml(mi)}</option>`));
                } else {
                    const allMicros = new Set();
                    for (const list of macroToMicros.values()) list.forEach(v => allMicros.add(v));
                    microOptions.push(...Array.from(allMicros).map(mi => `<option value="${escapeHtml(mi)}">${escapeHtml(mi)}</option>`));
                }
                microSel.innerHTML = microOptions.join('');
            }
            const filtered = applyBrowseFilters(window.__browseData);
            renderFilteredBrowse(filtered);
        };
    });
}

function applyBrowseFilters(data) {
    const docValue = document.getElementById('filterDocument')?.value || '';
    const macroValue = document.getElementById('filterMacro')?.value || '';
    const microValue = document.getElementById('filterMicro')?.value || '';
    const typeValue = document.getElementById('filterType')?.value || '';
    const diffValue = document.getElementById('filterDifficulty')?.value || '';

    const filtered = { documents: [] };
    const isDemo = (title) => {
        const t = (title || '').toLowerCase();
        return t.includes('demo') || t.includes('sample') || t.includes('example');
    };

    data.documents.forEach(d => {
        const name = d.title || d.name;
        if (isDemo(name)) return; // skip demo/sample docs
        if (docValue && name !== docValue) return;
        if (d.macros) {
            const newDoc = { title: d.title, name: d.name, document_id: d.document_id, macros: [] };
            d.macros.forEach(m => {
                if (macroValue && m.macro_topic_name !== macroValue) return;
                const newMicroList = [];
                m.micro_topics.forEach(mi => {
                    if (microValue && mi.micro_topic_name !== microValue) return;
                    const cards = (mi.cards || []).filter(c => {
                        if (typeValue && c.type !== typeValue) return false;
                        if (diffValue && (c.difficulty || '').toLowerCase() !== diffValue) return false;
                        return true;
                    });
                    newMicroList.push({ micro_topic_id: mi.micro_topic_id, micro_topic_name: mi.micro_topic_name, card_count: cards.length, cards });
                });
                if (newMicroList.length) newDoc.macros.push({ macro_topic_id: m.macro_topic_id, macro_topic_name: m.macro_topic_name, micro_topics: newMicroList });
            });
            if (newDoc.macros.length) filtered.documents.push(newDoc);
        } else if (d.topics) {
            // Legacy path: interpret left of name as macro, right as micro
            const newDoc = { title: d.title, name: d.name, document_id: d.document_id, topics: [] };
            d.topics.forEach(t => {
                const parts = (t.name || '').split(' - ');
                const macro = parts[0] || 'Uncategorized';
                const micro = parts[1] || 'General';
                if (macroValue && macro !== macroValue) return;
                if (microValue && micro !== microValue) return;
                const newTopic = { name: t.name, cards: [] };
                (t.cards || []).forEach(c => {
                    if (typeValue && c.type !== typeValue) return;
                    if (diffValue && (c.difficulty || '').toLowerCase() !== diffValue) return;
                    newTopic.cards.push(c);
                });
                if (newTopic.cards.length) newDoc.topics.push(newTopic);
            });
            if (newDoc.topics.length) filtered.documents.push(newDoc);
        }
    });
    return filtered;
}

function renderFilteredBrowse(filtered) {
    const browseContent = document.getElementById("browseContent");
    let html = "";
    for (const doc of filtered.documents) {
        html += `
            <div class="document-section">
                <div class="document-header">${escapeHtml(doc.title || doc.name)}</div>
        `;
        if (doc.macros) {
            doc.macros.forEach(m => {
                html += `
                    <div class="topic-section">
                        <div class="topic-header">🏷️ ${escapeHtml(m.macro_topic_name)}</div>
                `;
                m.micro_topics.forEach(mi => {
                    html += `
                        <div class="topic-section micro-section" data-micro="${escapeHtml(mi.micro_topic_name)}">
                            <div class="topic-header">📚 ${escapeHtml(mi.micro_topic_name)} <span class="count-badge">(${mi.card_count} cards)</span>
                                <button class="toggle-btn" onclick="toggleMicroSection(this)">Show</button>
                            </div>
                            <div class="cards-grid">
                    `;
                    (mi.cards || []).forEach(card => {
                        const type = (card.type || '').toLowerCase();
                        const typeClass = `card-type-${type}`;
                        let front = card.front || '';
                        let optionsHtml = '';
                        if (type === 'mcq') {
                            const parts = front.split('\n');
                            const optStart = parts.findIndex(l => l.trim().toLowerCase().startsWith('options:'));
                            if (optStart !== -1) {
                                const question = parts.slice(0, optStart).join('\n');
                                const optionLines = parts.slice(optStart + 1).filter(Boolean);
                                front = question;
                                if (optionLines.length) {
                                    optionsHtml = '<ul class="mcq-options">' + optionLines.map(line => `<li>${escapeHtml(line)}</li>`).join('') + '</ul>';
                                }
                            }
                        }
                        html += `
                            <div class="card-item">
                                <div class="card-header">
                                    <span class="card-type-badge ${typeClass}">${type}</span>
                                    <span class="card-difficulty">Difficulty: ${(card.difficulty || 'N/A')}</span>
                                </div>
                                <div class="card-front">Q: ${escapeHtml(front)}</div>
                                ${optionsHtml}
                                <div class="card-back">A: ${escapeHtml(card.back || '')}</div>
                            </div>
                        `;
                    });
                    html += `</div></div>`;
                });
                html += `</div>`;
            });
        } else if (doc.topics) {
            const total = doc.topics.reduce((acc,t)=>acc+(t.cards?.length||0),0);
            html += `<div class="document-info">Total Cards: ${total}</div>`;
            for (const topic of doc.topics) {
                html += `
                    <div class="topic-section micro-section" data-topic="${escapeHtml(topic.name)}">
                        <div class="topic-header">📚 ${escapeHtml(topic.name)} <span class="count-badge">(${(topic.cards?.length || 0)} cards)</span>
                            <button class="toggle-btn" onclick="toggleMicroSection(this)">Show</button>
                        </div>
                        <div class="cards-grid">
                `;
                for (const card of topic.cards) {
                    const type = (card.type || '').toLowerCase();
                    const typeClass = `card-type-${type}`;
                    let front = card.front || '';
                    let optionsHtml = '';
                    if (type === 'mcq') {
                        const parts = front.split('\n');
                        const optStart = parts.findIndex(l => l.trim().toLowerCase().startsWith('options:'));
                        if (optStart !== -1) {
                            const question = parts.slice(0, optStart).join('\n');
                            const optionLines = parts.slice(optStart + 1).filter(Boolean);
                            front = question;
                            if (optionLines.length) {
                                optionsHtml = '<ul class="mcq-options">' + optionLines.map(line => `<li>${escapeHtml(line)}</li>`).join('') + '</ul>';
                            }
                        }
                    }
                    html += `
                        <div class="card-item">
                            <div class="card-header">
                                <span class="card-type-badge ${typeClass}">${type}</span>
                                <span class="card-difficulty">Difficulty: ${(card.difficulty || 'N/A')}</span>
                            </div>
                            <div class="card-front">Q: ${escapeHtml(front)}</div>
                            ${optionsHtml}
                            <div class="card-back">A: ${escapeHtml(card.back || '')}</div>
                        </div>
                    `;
                }
                html += `</div></div>`;
            }
        }
        html += `</div>`;
    }
    browseContent.innerHTML = html || "<p class='info'>No cards match the selected filters.</p>";
}

function clearBrowseFilters() {
    ['filterDocument','filterMacro','filterMicro','filterType','filterDifficulty'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    const filtered = applyBrowseFilters(window.__browseData || {documents: []});
    renderFilteredBrowse(filtered);
}

function toggleMicroSection(btn) {
    const section = btn.closest('.micro-section');
    if (!section) return;
    const expanded = section.classList.toggle('expanded');
    btn.textContent = expanded ? 'Hide' : 'Show';
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Check progress for a document
 */
async function checkProgress() {
    const docIdInput = document.getElementById("docId");
    const progressResultElement = document.getElementById("progressResult");
    
    // Clear previous result
    progressResultElement.textContent = "";
    progressResultElement.className = "status-message";
    
    const docId = docIdInput.value.trim();
    
    // Validate document ID
    if (!docId) {
        progressResultElement.textContent = "Please enter a document ID.";
        progressResultElement.classList.add("error");
        return;
    }
    
    // Show loading state
    progressResultElement.textContent = "Loading progress...";
    progressResultElement.classList.add("info");
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/progress/document/${encodeURIComponent(docId)}`);
        
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error("Document not found");
            }
            throw new Error(`Failed to load progress: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Display progress
        const masteryPercent = data.mastery_percent.toFixed(1);
        progressResultElement.textContent = `Progress for "${data.title}": ${masteryPercent}%`;
        progressResultElement.classList.remove("info");
        progressResultElement.classList.add("success");
        
    } catch (error) {
        console.error("Error checking progress:", error);
        progressResultElement.textContent = `Error: ${error.message}`;
        progressResultElement.classList.remove("info");
        progressResultElement.classList.add("error");
    }
}

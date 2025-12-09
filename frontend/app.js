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

    // Auto-load content for progress tab
    if (tabName === 'progress') {
        populateProgressDocumentFilter();
        refreshProgressStats();
    }

    // Auto-load content for study tab
    if (tabName === 'study') {
        populateStudyDocumentFilter();
    }

    // Auto-load content for quiz tab
    if (tabName === 'quiz') {
        populateQuizDocumentFilter();
    }
}

/**
 * Upload a PDF file to the backend
 */
async function uploadPdf() {
    const fileInput = document.getElementById("pdfFile");
    const statusElement = document.getElementById("uploadStatus");
    const loadingAnimation = document.getElementById("loadingAnimation");
    const estimatedTimeEl = document.getElementById("estimatedTime");

    // Clear previous status
    statusElement.textContent = "";
    statusElement.className = "status-message";
    loadingAnimation.style.display = "none";

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

    // Estimate time based on file size
    const fileSizeMB = file.size / (1024 * 1024);
    let estimatedTime = "1-2 minutes";
    if (fileSizeMB < 1) {
        estimatedTime = "30-60 seconds";
    } else if (fileSizeMB < 5) {
        estimatedTime = "1-2 minutes";
    } else if (fileSizeMB < 10) {
        estimatedTime = "2-3 minutes";
    } else {
        estimatedTime = "3-5 minutes";
    }
    estimatedTimeEl.textContent = estimatedTime;

    // Show loading animation with image cycling
    loadingAnimation.style.display = "block";
    statusElement.style.display = "none";
    
    // Start cycling between Handsome Dan images
    const handsomeDanImg = document.getElementById("handsomeDan");
    const images = ['images/handsome-dan-1.png', 'images/handsome-dan-2.png'];
    let currentImageIndex = 0;
    let imageInterval = null;
    
    // Add error handler for image loading failures
    handsomeDanImg.onerror = function() {
        console.warn("Image failed to load, using emoji fallback");
        // If images don't exist, fall back to emoji
        this.onerror = null; // Prevent infinite loop
        this.alt = "🐕";
        this.style.fontSize = "3rem";
    };
    
    imageInterval = setInterval(() => {
        currentImageIndex = (currentImageIndex + 1) % images.length;
        handsomeDanImg.src = images[currentImageIndex];
    }, 1000); // Switch every 1 second

    try {
        // Create form data
        const formData = new FormData();
        formData.append("file", file);

        // Upload the file with longer timeout for AI flashcard generation
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 600000); // 10 minute timeout for AI generation

        const response = await fetch(`${API_BASE_URL}/api/upload/pdf`, {
            method: "POST",
            body: formData,
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        // Hide loading animation and stop image cycling
        clearInterval(imageInterval);
        loadingAnimation.style.display = "none";
        statusElement.style.display = "block";

        if (!response.ok) {
            throw new Error(`Upload failed: ${response.statusText}`);
        }

        const data = await response.json();

        // Store document ID globally
        currentDocumentId = data.document_id;

        // Update the document ID input in the Progress section if it exists
        const docIdInput = document.getElementById("docId");
        if (docIdInput) {
            docIdInput.value = data.document_id;
        }

        // Update study mode indicator if it exists
        const modeIndicator = document.getElementById("studyMode");
        if (modeIndicator) {
            modeIndicator.textContent = `📖 Ready to study: ${data.title}`;
            modeIndicator.className = "study-mode-indicator success";
        }

        // Show success message with chatbot status
        let message = `✓ Uploaded "${data.title}". Document ID: ${data.document_id}. Cards created: ${data.cards_created}.`;
        
        if (!data.chatbot_enabled) {
            message += `\n\n⚠️ Warning: Study Chat feature not available for this document (RAG indexing failed). Flashcard study mode will work normally.`;
        } else {
            message += `\n\n✓ Study Chat enabled (${data.chunks_created} text chunks indexed).`;
        }
        
        statusElement.textContent = message;
        statusElement.classList.add("success");

        // Clear file input
        fileInput.value = "";

    } catch (error) {
        console.error("Upload error:", error);

        // Hide loading animation and stop image cycling
        clearInterval(imageInterval);
        loadingAnimation.style.display = "none";
        statusElement.style.display = "block";

        // Check if it was a timeout/abort error
        if (error.name === 'AbortError') {
            statusElement.textContent = `Upload timed out. The AI is taking longer than expected to generate flashcards. Please try a smaller PDF or wait and refresh the page.`;
        } else {
            statusElement.textContent = `Error uploading PDF: ${error.message}`;
        }
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
    const nextCardButton = document.querySelector('.study-controls .primary-button');
    const revealButton = document.getElementById('revealButton');

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

    // Get selected document from dropdown
    const docSelect = document.getElementById("studyDocFilter");
    const selectedDocId = docSelect ? docSelect.value : null;
    currentDocumentId = selectedDocId || null;

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

        // Show appropriate button based on card type
        const nextCardBtn = document.querySelector('.study-controls .primary-button');
        const revealBtn = document.getElementById('revealButton');

        if (type === 'mcq' || type === 'cloze') {
            // For MCQ and Cloze, hide both buttons (they submit answers directly)
            if (nextCardBtn) nextCardBtn.style.display = 'none';
            if (revealBtn) revealBtn.style.display = 'none';
        } else {
            // For Definition/Application, show Reveal Answer button
            if (nextCardBtn) nextCardBtn.style.display = 'none';
            if (revealBtn) revealBtn.style.display = 'inline-block';
        }

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
        revealButton.style.display = 'none';
    }

    // Hide Next Card button when clearing (will be shown by loadNextCard after card loads)
    const nextCardButton = document.querySelector('.study-controls .primary-button');
    if (nextCardButton) {
        nextCardButton.style.display = 'none';
    }
}/**
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

    // Show the answer with a label
    if (studyAnswerEl) {
        // Create answer content with label
        const answerLabel = document.createElement('div');
        answerLabel.style.fontSize = '0.875rem';
        answerLabel.style.color = 'var(--warm-gray-600)';
        answerLabel.style.fontWeight = '600';
        answerLabel.style.marginBottom = '0.5rem';
        answerLabel.style.textTransform = 'uppercase';
        answerLabel.style.letterSpacing = '0.05em';
        answerLabel.textContent = '✓ Answer';

        studyAnswerEl.innerHTML = '';
        studyAnswerEl.appendChild(answerLabel);

        // Add answer text
        const answerText = document.createElement('div');
        answerText.textContent = currentCardData.back || '';
        studyAnswerEl.appendChild(answerText);

        studyAnswerEl.style.display = 'block';
    }

    // Hide reveal button, show Next Card button
    if (revealButton) {
        revealButton.style.display = 'none';
    }

    const nextCardButton = document.querySelector('.study-controls .primary-button');
    if (nextCardButton) {
        nextCardButton.style.display = 'inline-block';
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

        // After answer is submitted and graded, update UI to show next card option
        // Hide the answer input sections
        const textAnswerSection = document.getElementById("textAnswerSection");
        const mcqOptions = document.getElementById("mcqOptions");
        const selfGradeSection = document.getElementById("selfGradeSection");
        
        if (textAnswerSection) textAnswerSection.style.display = 'none';
        if (mcqOptions) mcqOptions.style.display = 'none';
        if (selfGradeSection) selfGradeSection.style.display = 'none';

        // Show the correct answer
        const studyAnswerEl = document.getElementById("studyAnswer");
        if (studyAnswerEl && currentCardData) {
            const answerLabel = document.createElement('div');
            answerLabel.style.fontWeight = '600';
            answerLabel.style.color = 'var(--primary-color)';
            answerLabel.style.marginBottom = '0.5rem';
            answerLabel.style.textTransform = 'uppercase';
            answerLabel.style.letterSpacing = '0.05em';
            answerLabel.textContent = '✓ Correct Answer';

            studyAnswerEl.innerHTML = '';
            studyAnswerEl.appendChild(answerLabel);

            // Add answer text
            const answerText = document.createElement('div');
            answerText.textContent = currentCardData.back || '';
            studyAnswerEl.appendChild(answerText);

            studyAnswerEl.style.display = 'block';
        }

        // Hide reveal button, show Next Card button
        const revealButton = document.getElementById("revealButton");
        if (revealButton) {
            revealButton.style.display = 'none';
        }

        const nextCardButton = document.querySelector('.study-controls .primary-button');
        if (nextCardButton) {
            nextCardButton.style.display = 'inline-block';
        }

    } catch (error) {
        console.error("Error submitting answer:", error);
        feedbackElement.textContent = `Error submitting answer: ${error.message}`;
        feedbackElement.classList.remove("info");
        feedbackElement.classList.add("error");
    }
}

/**
 * Populate document filter dropdown in study tab
 */
async function populateStudyDocumentFilter() {
    const docSelect = document.getElementById("studyDocFilter");
    if (!docSelect) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/progress/browse`);
        if (!response.ok) {
            throw new Error(`Failed to load documents: ${response.statusText}`);
        }

        const data = await response.json();

        // Filter out demo/sample documents
        const isDemo = (title) => {
            const t = (title || '').toLowerCase();
            return t.includes('demo') || t.includes('sample') || t.includes('example');
        };

        const realDocs = (data.documents || []).filter(d => !isDemo(d.title || d.name));

        // Build options
        const options = ['<option value="">All Documents</option>'];
        realDocs.forEach(d => {
            const name = d.title || d.name;
            const id = d.document_id;
            options.push(`<option value="${id}">${escapeHtml(name)}</option>`);
        });

        docSelect.innerHTML = options.join('');
    } catch (error) {
        console.error("Error loading documents for study filter:", error);
    }
}

/**
 * Change study document based on dropdown selection
 */
function changeStudyDocument() {
    const docSelect = document.getElementById("studyDocFilter");
    const modeIndicator = document.getElementById("studyMode");

    if (!docSelect) return;

    currentDocumentId = docSelect.value || null;

    // Update mode indicator
    if (currentDocumentId) {
        const selectedOption = docSelect.options[docSelect.selectedIndex];
        const docName = selectedOption ? selectedOption.text : "Document";
        modeIndicator.textContent = `📖 Studying: ${docName}`;
        modeIndicator.className = "study-mode-indicator info";
    } else {
        modeIndicator.textContent = "📚 Studying all documents";
        modeIndicator.className = "study-mode-indicator info";
    }

    // Clear the card display
    document.getElementById("cardFront").textContent = "Click 'Next Card' to start studying.";
    document.getElementById("answerInput").value = "";
    document.getElementById("feedback").textContent = "";
    document.getElementById("feedback").className = "feedback";

    // Clear answer sections
    clearAnswerSections();

    // Show Next Card button for initial state
    const nextCardButton = document.querySelector('.study-controls .primary-button');
    if (nextCardButton) {
        nextCardButton.style.display = 'inline-block';
    }
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

    // Helper function to build macro/micro options based on selected document
    const buildMacroMicroOptions = (selectedDoc) => {
        console.log('[FILTER] Building macro/micro for document:', selectedDoc || 'ALL');
        const macrosSet = new Set();
        const macroToMicros = new Map();

        // Filter data by selected document (or all if none selected)
        const filteredDocs = selectedDoc
            ? data.documents.filter(d => (d.title || d.name) === selectedDoc)
            : data.documents.filter(d => !isDemo(d.title || d.name));

        console.log('[FILTER] Filtered to', filteredDocs.length, 'documents');

        filteredDocs.forEach(d => {
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

        return { macrosSet, macroToMicros };
    };

    // Initial population (all documents)
    let { macrosSet, macroToMicros } = buildMacroMicroOptions('');
    const macroOptions = ['<option value="">All Macros</option>', ...Array.from(macrosSet).map(m => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`)];
    macroSel.innerHTML = macroOptions.join('');

    // Initialize micros
    const allMicros = new Set();
    for (const list of macroToMicros.values()) {
        list.forEach(v => allMicros.add(v));
    }
    const microOptions = ['<option value="">All Micros</option>', ...Array.from(allMicros).map(mi => `<option value="${escapeHtml(mi)}">${escapeHtml(mi)}</option>`)];
    microSel.innerHTML = microOptions.join('');

    ['filterDocument','filterMacro','filterMicro','filterType','filterDifficulty'].forEach(id => {
        const el = document.getElementById(id);
        el.onchange = () => {
            // Rebuild macros and micros when document changes
            if (id === 'filterDocument') {
                const selectedDoc = docSel.value;
                const { macrosSet, macroToMicros } = buildMacroMicroOptions(selectedDoc);

                // Rebuild macros dropdown
                const macroOptions = ['<option value="">All Macros</option>', ...Array.from(macrosSet).map(m => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`)];
                macroSel.innerHTML = macroOptions.join('');

                // Rebuild micros dropdown
                const allMicros = new Set();
                for (const list of macroToMicros.values()) list.forEach(v => allMicros.add(v));
                const microOptions = ['<option value="">All Micros</option>', ...Array.from(allMicros).map(mi => `<option value="${escapeHtml(mi)}">${escapeHtml(mi)}</option>`)];
                microSel.innerHTML = microOptions.join('');
            }

            // Rebuild micros when macro changes
            if (id === 'filterMacro') {
                const selectedDoc = docSel.value;
                const { macroToMicros } = buildMacroMicroOptions(selectedDoc);

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
    const docSelect = document.getElementById("progressDocFilter");
    const progressResultElement = document.getElementById("progressResult");

    // Clear previous result
    progressResultElement.textContent = "";
    progressResultElement.className = "status-message";

    const docId = docSelect.value.trim();

    // Validate document selection
    if (!docId) {
        progressResultElement.textContent = "Please select a document.";
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

/**
 * Load and display mastery distribution (cards by mastery level 0-3)
 */
async function loadMasteryDistribution(documentId = null) {
    const masteryContainer = document.getElementById("masteryDistribution");

    if (!masteryContainer) return;

    masteryContainer.innerHTML = "<p class='info'>Loading mastery data...</p>";

    try {
        const url = documentId
            ? `${API_BASE_URL}/api/progress/mastery-distribution?document_id=${encodeURIComponent(documentId)}`
            : `${API_BASE_URL}/api/progress/mastery-distribution`;

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`Failed to load mastery data: ${response.statusText}`);
        }

        const data = await response.json();

        const total = data.total_studied + data.never_seen;

        // Calculate percentages for each level
        const getPercent = (count) => total > 0 ? ((count / total) * 100).toFixed(1) : 0;

        // Create mastery bars display
        const html = `
            <div class="mastery-bars">
                <div class="mastery-bar-item">
                    <div class="mastery-bar-header">
                        <span class="mastery-label">Level 3 - Perfect</span>
                        <span class="mastery-count">${data.level_3} cards (${getPercent(data.level_3)}%)</span>
                    </div>
                    <div class="mastery-bar-track">
                        <div class="mastery-bar-fill level-3" style="width: ${getPercent(data.level_3)}%"></div>
                    </div>
                </div>
                <div class="mastery-bar-item">
                    <div class="mastery-bar-header">
                        <span class="mastery-label">Level 2 - Good</span>
                        <span class="mastery-count">${data.level_2} cards (${getPercent(data.level_2)}%)</span>
                    </div>
                    <div class="mastery-bar-track">
                        <div class="mastery-bar-fill level-2" style="width: ${getPercent(data.level_2)}%"></div>
                    </div>
                </div>
                <div class="mastery-bar-item">
                    <div class="mastery-bar-header">
                        <span class="mastery-label">Level 1 - Barely</span>
                        <span class="mastery-count">${data.level_1} cards (${getPercent(data.level_1)}%)</span>
                    </div>
                    <div class="mastery-bar-track">
                        <div class="mastery-bar-fill level-1" style="width: ${getPercent(data.level_1)}%"></div>
                    </div>
                </div>
                <div class="mastery-bar-item">
                    <div class="mastery-bar-header">
                        <span class="mastery-label">Level 0 - No Idea</span>
                        <span class="mastery-count">${data.level_0} cards (${getPercent(data.level_0)}%)</span>
                    </div>
                    <div class="mastery-bar-track">
                        <div class="mastery-bar-fill level-0" style="width: ${getPercent(data.level_0)}%"></div>
                    </div>
                </div>
                <div class="mastery-bar-item">
                    <div class="mastery-bar-header">
                        <span class="mastery-label">Never Seen</span>
                        <span class="mastery-count">${data.never_seen} cards (${getPercent(data.never_seen)}%)</span>
                    </div>
                    <div class="mastery-bar-track">
                        <div class="mastery-bar-fill never-seen" style="width: ${getPercent(data.never_seen)}%"></div>
                    </div>
                </div>
            </div>
        `;

        masteryContainer.innerHTML = html;

    } catch (error) {
        console.error("Error loading mastery distribution:", error);
        masteryContainer.innerHTML = `<p class='error'>Error loading mastery data: ${error.message}</p>`;
    }
}

/**
 * Populate document filter dropdown in progress tab
 */
async function populateProgressDocumentFilter() {
    const docSelect = document.getElementById("progressDocFilter");
    if (!docSelect) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/progress/browse`);
        if (!response.ok) {
            throw new Error(`Failed to load documents: ${response.statusText}`);
        }

        const data = await response.json();

        // Filter out demo/sample documents
        const isDemo = (title) => {
            const t = (title || '').toLowerCase();
            return t.includes('demo') || t.includes('sample') || t.includes('example');
        };

        const realDocs = (data.documents || []).filter(d => !isDemo(d.title || d.name));

        // Build options
        const options = ['<option value="">All Documents</option>'];
        realDocs.forEach(d => {
            const name = d.title || d.name;
            const id = d.document_id; // Use document_id from browse endpoint
            options.push(`<option value="${id}">${escapeHtml(name)}</option>`);
        });

        docSelect.innerHTML = options.join('');
    } catch (error) {
        console.error("Error loading documents for progress filter:", error);
    }
}

/**
 * Refresh all progress statistics based on selected document
 */
function refreshProgressStats() {
    const docSelect = document.getElementById("progressDocFilter");
    const documentId = docSelect ? docSelect.value : null;

    // Update title based on selection
    const statsTitle = document.getElementById("statsTitle");
    if (statsTitle) {
        if (documentId) {
            const selectedOption = docSelect.options[docSelect.selectedIndex];
            const docName = selectedOption ? selectedOption.text : "Document";
            statsTitle.textContent = `📊 Statistics - ${docName}`;
        } else {
            statsTitle.textContent = "📊 Overall Statistics";
        }
    }

    // Load stats with document filter
    loadOverallStats(documentId);
    loadMasteryDistribution(documentId);
    loadSpacedRepetitionMetrics(documentId);

    // Show/hide macro topics section (only show when viewing a specific document)
    const macroTopicsSection = document.getElementById("macroTopicsSection");
    if (macroTopicsSection) {
        if (documentId) {
            macroTopicsSection.style.display = "block";
            loadMacroTopicsProgress(documentId);
        } else {
            macroTopicsSection.style.display = "none";
        }
    }
}

/**
 * Load and display overall statistics
 */
async function loadOverallStats(documentId = null) {
    const statsContainer = document.getElementById("overallStats");

    if (!statsContainer) return;

    statsContainer.innerHTML = "<p class='info'>Loading statistics...</p>";

    try {
        const url = documentId
            ? `${API_BASE_URL}/api/progress/overall?document_id=${encodeURIComponent(documentId)}`
            : `${API_BASE_URL}/api/progress/overall`;

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`Failed to load stats: ${response.statusText}`);
        }

        const data = await response.json();

        // Create stats display
        const html = `
            <div class="stat-card">
                <div class="stat-label">Total Cards: <span class="stat-value">${data.total_cards}</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Cards Studied: <span class="stat-value">${data.cards_studied}</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Never Seen: <span class="stat-value">${data.cards_never_seen}</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Progress: <span class="stat-value">${data.percent_studied}%</span></div>
            </div>
        `;

        statsContainer.innerHTML = html;

    } catch (error) {
        console.error("Error loading overall stats:", error);
        statsContainer.innerHTML = `<p class='error'>Error loading statistics: ${error.message}</p>`;
    }
}

/**
 * Load and display progress for macro topics in a document
 */
async function loadMacroTopicsProgress(documentId) {
    const container = document.getElementById("macroTopicsProgress");

    if (!container || !documentId) return;

    container.innerHTML = "<p class='info'>Loading macro topics...</p>";

    try {
        const response = await fetch(`${API_BASE_URL}/api/progress/macro-topics-progress/${encodeURIComponent(documentId)}`);

        if (!response.ok) {
            throw new Error(`Failed to load macro topics progress: ${response.statusText}`);
        }

        const data = await response.json();

        if (!data.macros || data.macros.length === 0) {
            container.innerHTML = "<p class='info'>No macro topics found for this document.</p>";
            return;
        }

        // Create table display
        let html = `
            <table class="documents-progress-table">
                <thead>
                    <tr>
                        <th>Macro Topic</th>
                        <th>Total Cards</th>
                        <th>Studied</th>
                        <th>Mastery</th>
                        <th>Last Studied</th>
                    </tr>
                </thead>
                <tbody>
        `;

        data.macros.forEach(macro => {
            const masteryClass = macro.mastery_percent >= 75 ? 'mastery-high' :
                                macro.mastery_percent >= 40 ? 'mastery-medium' : 'mastery-low';

            const lastStudied = macro.last_studied
                ? new Date(macro.last_studied).toLocaleDateString()
                : 'Never';

            html += `
                <tr class="macro-row">
                    <td class="doc-title">${escapeHtml(macro.name)}</td>
                    <td class="text-center">${macro.total_cards}</td>
                    <td class="text-center">${macro.cards_studied}</td>
                    <td class="text-center">
                        <span class="mastery-badge ${masteryClass}">${macro.mastery_percent}%</span>
                    </td>
                    <td class="text-center">${lastStudied}</td>
                </tr>
            `;
        });

        html += `
                </tbody>
            </table>
        `;

        container.innerHTML = html;

    } catch (error) {
        console.error("Error loading macro topics progress:", error);
        container.innerHTML = `<p class='error'>Error loading macro topics: ${error.message}</p>`;
    }
}

/**
 * Select a document from the progress table
 */
function selectDocumentFromTable(documentId) {
    const docSelect = document.getElementById("progressDocFilter");
    if (docSelect) {
        docSelect.value = documentId;
        refreshProgressStats();
    }
}

/**
 * Load and display spaced repetition metrics
 */
async function loadSpacedRepetitionMetrics(documentId = null) {
    const container = document.getElementById("spacedRepetitionMetrics");

    if (!container) return;

    container.innerHTML = "<p class='info'>Loading schedule...</p>";

    try {
        const url = documentId
            ? `${API_BASE_URL}/api/progress/spaced-repetition-metrics?document_id=${encodeURIComponent(documentId)}`
            : `${API_BASE_URL}/api/progress/spaced-repetition-metrics`;

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`Failed to load spaced repetition metrics: ${response.statusText}`);
        }

        const data = await response.json();

        // Create spaced repetition cards display
        const html = `
            <div class="spaced-rep-grid">
                <div class="spaced-rep-card due-today">
                    <div class="rep-icon">📅</div>
                    <div class="rep-value">${data.cards_due_today}</div>
                    <div class="rep-label">Due Today</div>
                    ${data.cards_overdue > 0 ? `<div class="rep-sublabel">${data.cards_overdue} overdue</div>` : ''}
                </div>
                <div class="spaced-rep-card due-soon">
                    <div class="rep-icon">📆</div>
                    <div class="rep-value">${data.cards_due_soon}</div>
                    <div class="rep-label">Due Next 7 Days</div>
                </div>
                <div class="spaced-rep-card avg-interval">
                    <div class="rep-icon">⏱️</div>
                    <div class="rep-value">${data.average_interval}</div>
                    <div class="rep-label">Avg Interval (days)</div>
                </div>
                <div class="spaced-rep-card retention">
                    <div class="rep-icon">🎯</div>
                    <div class="rep-value">${data.retention_rate}%</div>
                    <div class="rep-label">Retention Rate</div>
                </div>
            </div>
            <div class="spaced-rep-explanation">
                <p><strong>Avg Interval:</strong> The average time between reviews for studied cards. As you master cards, this number increases as the system spaces out reviews (e.g., 1→3→7→14 days).</p>
                <p><strong>Retention Rate:</strong> The percentage of reviews where you scored "Good" or "Perfect" (grades 2-3). Higher retention means you're successfully remembering the material.</p>
            </div>
            <div class="total-reviews-info">
                <span>📊 Total Reviews Completed: <strong>${data.total_reviews}</strong></span>
            </div>
        `;

        container.innerHTML = html;

    } catch (error) {
        console.error("Error loading spaced repetition metrics:", error);
        container.innerHTML = `<p class='error'>Error loading schedule: ${error.message}</p>`;
    }
}

/**
 * Quiz Bot Functions
 */

// Global quiz state
let currentQuizSessionId = null;
let currentQuizDocumentId = null;
let currentQuestionId = null;
let currentQuizCardId = null;
let conversationHistory = [];  // Track conversation for context
let selectedDocumentIds = [];  // Track multiple selected documents
let recognition = null;  // Speech recognition instance
let isRecording = false;

/**
 * Populate document filter dropdown in quiz tab
 */
async function populateQuizDocumentFilter() {
    const docList = document.getElementById("quizDocumentList");
    
    if (!docList) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/progress/browse`);
        if (!response.ok) {
            throw new Error(`Failed to load documents: ${response.statusText}`);
        }

        const data = await response.json();

        // Filter out demo/sample documents
        const isDemo = (title) => {
            const t = (title || '').toLowerCase();
            return t.includes('demo') || t.includes('sample') || t.includes('example');
        };

        const realDocs = (data.documents || []).filter(d => !isDemo(d.title || d.name));

        if (realDocs.length === 0) {
            docList.innerHTML = '<p style="color: var(--warm-gray-500); font-style: italic;">No documents uploaded yet. Upload a PDF first.</p>';
            return;
        }

        // Create checkbox list
        docList.innerHTML = realDocs.map(d => {
            const name = d.title || d.name;
            const id = d.document_id;
            const chatEnabled = d.chatbot_enabled || false;
            const statusIcon = chatEnabled ? '💬' : '⚠️';
            const statusTitle = chatEnabled ? 
                `Chat enabled (${d.chunk_count} chunks indexed)` : 
                'Chat not available - document not indexed properly';
            const statusClass = chatEnabled ? 'chat-enabled' : 'chat-disabled';
            
            return `
                <label class="document-checkbox ${statusClass}">
                    <input type="checkbox" value="${id}" onchange="updateSelectedDocuments()">
                    <span title="${statusTitle}">
                        ${statusIcon} ${escapeHtml(name)}
                    </span>
                </label>
            `;
        }).join('');

    } catch (error) {
        console.error("Error loading documents for quiz filter:", error);
        docList.innerHTML = '<p style="color: var(--error-text);">Error loading documents</p>';
    }
}

/**
 * Update selected documents array when checkboxes change
 */
function updateSelectedDocuments() {
    const checkboxes = document.querySelectorAll('#quizDocumentList input[type="checkbox"]:checked');
    selectedDocumentIds = Array.from(checkboxes).map(cb => cb.value);
    
    const startBtn = document.getElementById("startQuizBtn");
    startBtn.disabled = selectedDocumentIds.length === 0;
    
    // Update button text
    if (selectedDocumentIds.length > 1) {
        startBtn.textContent = `Start Chat (${selectedDocumentIds.length} documents)`;
    } else if (selectedDocumentIds.length === 1) {
        startBtn.textContent = "Start Chat";
    } else {
        startBtn.textContent = "Start Chat";
    }
}

/**
 * Start a new quiz session
 */
async function startQuiz() {
    const statusElement = document.getElementById("quizStatus");
    const chatContainer = document.getElementById("quizChatContainer");
    const startBtn = document.getElementById("startQuizBtn");
    const endBtn = document.getElementById("endQuizBtn");
    const messagesContainer = document.getElementById("quizMessages");

    if (selectedDocumentIds.length === 0) {
        statusElement.textContent = "Please select at least one document first.";
        statusElement.className = "status-message error";
        return;
    }

    // Clear previous state
    statusElement.textContent = "Starting chat...";
    statusElement.className = "status-message info";

    try {
        const requestBody = {
            user_id: "default_user"
        };
        
        // Send either single document_id or multiple document_ids
        if (selectedDocumentIds.length === 1) {
            requestBody.document_id = selectedDocumentIds[0];
        } else {
            requestBody.document_ids = selectedDocumentIds;
        }

        const response = await fetch(`${API_BASE_URL}/api/quiz/start`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`Failed to start chat: ${response.statusText}`);
        }

        const data = await response.json();
        currentQuizSessionId = data.session_id;

        // Update UI
        statusElement.textContent = data.message;
        statusElement.className = "status-message success";
        chatContainer.style.display = "block";
        startBtn.style.display = "none";
        endBtn.style.display = "inline-block";

        // Clear messages and reset stats
        messagesContainer.innerHTML = "";
        conversationHistory = [];  // Reset conversation history
        document.getElementById("quizQuestionsCount").textContent = "0";
        document.getElementById("quizDocsCount").textContent = selectedDocumentIds.length.toString();
        document.getElementById("quizCorrectCount").textContent = "0";

        // Add welcome message
        const docText = selectedDocumentIds.length === 1 ? "this document" : `these ${selectedDocumentIds.length} documents`;
        addQuizMessage("bot", `Chat started! Ask me anything about ${docText}. I'll provide answers with citations from your course materials.`, "Study Assistant 🤖");

        // Enable input for chat
        const answerInput = document.getElementById("quizAnswerInput");
        answerInput.disabled = false;
        answerInput.placeholder = "Ask a question about the course material...";
        answerInput.focus();

    } catch (error) {
        console.error("Error starting quiz:", error);
        statusElement.textContent = `Error: ${error.message}`;
        statusElement.className = "status-message error";
    }
}

/**
 * Submit quiz answer - now functions as conversational chat
 */
async function submitQuizAnswer() {
    const answerInput = document.getElementById("quizAnswerInput");
    const userMessage = answerInput.value.trim();

    if (!userMessage) {
        return;  // Don't submit empty messages
    }

    if (!currentQuizSessionId) {
        alert("No active chat session. Please start a quiz first.");
        return;
    }

    // Display user message
    addQuizMessage("user", userMessage, "You");

    // Add to conversation history
    conversationHistory.push({
        role: "user",
        content: userMessage
    });

    // Clear input and disable while processing
    answerInput.value = "";
    answerInput.disabled = true;

    try {
        const requestBody = {
            session_id: currentQuizSessionId,
            message: userMessage,
            conversation_history: conversationHistory
        };
        
        // Include document_ids if multiple documents selected
        if (selectedDocumentIds.length > 0) {
            requestBody.document_ids = selectedDocumentIds;
        }
        
        const response = await fetch(`${API_BASE_URL}/api/quiz/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`Failed to get response: ${response.statusText}`);
        }

        const data = await response.json();

        // Display bot response
        let responseContent = data.response;
        
        // Add citations if available
        if (data.citations) {
            responseContent += `\n\n📚 **Sources:**\n${data.citations}`;
        }
        
        addQuizMessage("bot", responseContent, "Study Assistant 🤖");

        // Update sources count
        if (data.sources && data.sources.length > 0) {
            document.getElementById("quizCorrectCount").textContent = data.sources.length.toString();
        }

        // Add assistant response to conversation history
        conversationHistory.push({
            role: "assistant",
            content: data.response
        });

        // Display follow-up questions if available
        if (data.follow_up_questions && data.follow_up_questions.length > 0) {
            const followUpsDiv = document.createElement("div");
            followUpsDiv.className = "follow-up-questions";
            followUpsDiv.innerHTML = "<strong>💡 You might also ask:</strong>";
            
            data.follow_up_questions.forEach(question => {
                const btn = document.createElement("button");
                btn.className = "follow-up-btn";
                btn.textContent = question;
                btn.onclick = () => {
                    answerInput.value = question;
                    submitQuizAnswer();
                };
                followUpsDiv.appendChild(btn);
            });
            
            const messagesContainer = document.getElementById("quizMessages");
            messagesContainer.appendChild(followUpsDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        // Re-enable input
        answerInput.disabled = false;
        answerInput.focus();

        // Update interaction count
        const questionsCount = document.getElementById("quizQuestionsCount");
        questionsCount.textContent = parseInt(questionsCount.textContent) + 1;

    } catch (error) {
        console.error("Error getting response:", error);
        addQuizMessage("bot", `Sorry, I encountered an error: ${error.message}`, "Error ❌");
        answerInput.disabled = false;
    }
}

/**
 * Add message to quiz chat
 */
function addQuizMessage(type, content, header, scoreClass = null) {
    const messagesContainer = document.getElementById("quizMessages");
    
    const messageDiv = document.createElement("div");
    messageDiv.className = `quiz-message ${type}`;
    
    const headerDiv = document.createElement("div");
    headerDiv.className = "quiz-message-header";
    headerDiv.innerHTML = `<span>${header}</span>`;
    
    if (scoreClass) {
        const badge = document.createElement("span");
        badge.className = `quiz-score-badge ${scoreClass}`;
        badge.textContent = scoreClass.toUpperCase();
        headerDiv.appendChild(badge);
    }
    
    const contentDiv = document.createElement("div");
    contentDiv.className = "quiz-message-content";
    
    // Convert basic markdown formatting for better readability
    let formattedContent = content
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')  // Bold
        .replace(/\n\n/g, '<br><br>')  // Paragraphs
        .replace(/\n/g, '<br>')  // Line breaks
        .replace(/\[(\d+)\]/g, '<span class="citation">[$1]</span>');  // Citations
    
    contentDiv.innerHTML = formattedContent;
    
    messageDiv.appendChild(headerDiv);
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Update quiz statistics display
 */
async function updateQuizStats() {
    if (!currentQuizSessionId) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/quiz/history/${currentQuizSessionId}`);
        
        if (!response.ok) {
            throw new Error(`Failed to load stats: ${response.statusText}`);
        }

        const data = await response.json();

        document.getElementById("quizQuestionsCount").textContent = data.questions_asked;
        document.getElementById("quizCorrectCount").textContent = data.questions_correct;
        document.getElementById("quizAvgScore").textContent = data.average_score.toFixed(1);

    } catch (error) {
        console.error("Error updating quiz stats:", error);
    }
}

/**
 * End quiz session
 */
async function endQuiz() {
    if (!currentQuizSessionId) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/quiz/end/${currentQuizSessionId}`, {
            method: "POST"
        });

        if (response.ok) {
            const chatContainer = document.getElementById("quizChatContainer");
            const startBtn = document.getElementById("startQuizBtn");
            const endBtn = document.getElementById("endQuizBtn");
            const statusElement = document.getElementById("quizStatus");

            chatContainer.style.display = "none";
            startBtn.style.display = "inline-block";
            endBtn.style.display = "none";
            
            statusElement.textContent = "Chat ended. Select a document to start a new session.";
            statusElement.className = "status-message info";

            currentQuizSessionId = null;
            currentQuestionId = null;
            conversationHistory = [];  // Reset conversation
            selectedDocumentIds = [];  // Reset selected documents
        }
    } catch (error) {
        console.error("Error ending quiz:", error);
    }
}

/**
 * Voice Input Functions
 */

/**
 * Initialize speech recognition
 */
function initSpeechRecognition() {
    // Check browser support
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
        console.warn("Speech recognition not supported in this browser");
        const voiceBtn = document.getElementById("voiceInputBtn");
        if (voiceBtn) {
            voiceBtn.style.display = "none";
        }
        return null;
    }
    
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
    
    recognition.onstart = () => {
        isRecording = true;
        const indicator = document.getElementById("voiceRecordingIndicator");
        const voiceBtn = document.getElementById("voiceInputBtn");
        if (indicator) indicator.style.display = "flex";
        if (voiceBtn) voiceBtn.classList.add("recording");
    };
    
    recognition.onend = () => {
        isRecording = false;
        const indicator = document.getElementById("voiceRecordingIndicator");
        const voiceBtn = document.getElementById("voiceInputBtn");
        if (indicator) indicator.style.display = "none";
        if (voiceBtn) voiceBtn.classList.remove("recording");
    };
    
    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        const answerInput = document.getElementById("quizAnswerInput");
        if (answerInput) {
            answerInput.value = transcript;
            answerInput.focus();
        }
    };
    
    recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
        isRecording = false;
        const indicator = document.getElementById("voiceRecordingIndicator");
        const voiceBtn = document.getElementById("voiceInputBtn");
        if (indicator) indicator.style.display = "none";
        if (voiceBtn) voiceBtn.classList.remove("recording");
        
        if (event.error === 'not-allowed') {
            alert("Microphone access denied. Please enable microphone permissions in your browser settings.");
        }
    };
    
    return recognition;
}

/**
 * Toggle voice input recording
 */
function toggleVoiceInput() {
    if (!recognition) {
        recognition = initSpeechRecognition();
        if (!recognition) {
            alert("Voice input is not supported in your browser. Please try Chrome or Edge.");
            return;
        }
    }
    
    if (isRecording) {
        // Stop recording
        recognition.stop();
    } else {
        // Start recording
        const answerInput = document.getElementById("quizAnswerInput");
        if (answerInput) {
            answerInput.value = "";  // Clear existing text
        }
        recognition.start();
    }
}

// Initialize speech recognition on page load
document.addEventListener('DOMContentLoaded', () => {
    initSpeechRecognition();
});

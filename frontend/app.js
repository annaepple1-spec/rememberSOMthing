// Global variables
let currentDocumentId = null;
let currentCardId = null;
const API_BASE_URL = "http://localhost:8000";

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
 * Load the next card for studying
 */
async function loadNextCard() {
    const cardFrontElement = document.getElementById("cardFront");
    const answerInput = document.getElementById("answerInput");
    const feedbackElement = document.getElementById("feedback");
    
    // Clear previous state
    answerInput.value = "";
    feedbackElement.textContent = "";
    feedbackElement.className = "feedback";
    currentCardId = null;
    
    // Show loading state
    cardFrontElement.textContent = "Loading next card...";
    
    try {
        // Build URL with optional document_id filter
        let url = `${API_BASE_URL}/api/session/next-card`;
        if (currentDocumentId) {
            url += `?document_id=${encodeURIComponent(currentDocumentId)}`;
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
        
        // Store card ID and display question
        currentCardId = card.id;
        cardFrontElement.textContent = card.front;
        
    } catch (error) {
        console.error("Error loading card:", error);
        cardFrontElement.textContent = `Error loading card: ${error.message}`;
    }
}

/**
 * Submit the user's answer for grading
 */
async function submitAnswer() {
    const answerInput = document.getElementById("answerInput");
    const feedbackElement = document.getElementById("feedback");
    
    // Clear previous feedback
    feedbackElement.textContent = "";
    feedbackElement.className = "feedback";
    
    // Validate that a card is loaded
    if (!currentCardId) {
        feedbackElement.textContent = "Please load a card first by clicking 'Next Card'.";
        feedbackElement.classList.add("warning");
        return;
    }
    
    const userAnswer = answerInput.value.trim();
    
    // Validate answer
    if (!userAnswer) {
        feedbackElement.textContent = "Please enter an answer before submitting.";
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
                latency_ms: 1000  // Hardcoded latency for demo
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
        
        // Populate filters and compute filtered view
        populateBrowseFilters(data);
        const filtered = applyBrowseFilters(data);
        let html = "";
        
        for (const doc of filtered.documents) {
            html += `
                <div class="document-section">
                    <div class="document-header">${escapeHtml(doc.title || doc.name)}</div>
                    <div class="document-info">${doc.document_id ? `Document ID: ${doc.document_id} | ` : ''}Total Cards: ${doc.total_cards ?? doc.topics.reduce((acc,t)=>acc+(t.cards?.length||0),0)}</div>
            `;
            
            // Add topics and cards
            for (const topic of doc.topics) {
                html += `
                    <div class="topic-section">
                        <div class="topic-header">📚 ${escapeHtml(topic.name)}</div>
                `;
                
                // Add cards
                for (const card of topic.cards) {
                    const typeClass = `card-type-${card.type}`;
                    html += `
                        <div class="card-item">
                            <div>
                                <span class="card-type-badge ${typeClass}">${card.type}</span>
                                <span class="card-difficulty">Difficulty: ${card.difficulty || 'N/A'}</span>
                            </div>
                            <div class="card-front">Q: ${escapeHtml(card.front)}</div>
                            <div class="card-back">A: ${escapeHtml(card.back)}</div>
                        </div>
                    `;
                }
                
                html += `</div>`; // Close topic-section
            }
            
            html += `</div>`; // Close document-section
        }
        
        browseContent.innerHTML = html;
        
    } catch (error) {
        console.error("Error loading cards:", error);
        browseContent.innerHTML = `<p class='error'>Error loading cards: ${error.message}</p>`;
    }
}

function populateBrowseFilters(data) {
    const docSel = document.getElementById('filterDocument');
    const topicSel = document.getElementById('filterTopic');
    const typeSel = document.getElementById('filterType');
    const diffSel = document.getElementById('filterDifficulty');

    if (!docSel || !topicSel || !typeSel || !diffSel) return;

    const docOptions = ['<option value="">All Documents</option>'];
    data.documents.forEach(d => {
        const name = d.title || d.name;
        docOptions.push(`<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`);
    });
    docSel.innerHTML = docOptions.join('');

    const topicsSet = new Set();
    data.documents.forEach(d => d.topics.forEach(t => topicsSet.add(t.name)));
    const topicOptions = ['<option value="">All Topics</option>', ...Array.from(topicsSet).map(t => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`)];
    topicSel.innerHTML = topicOptions.join('');

    ['filterDocument','filterTopic','filterType','filterDifficulty'].forEach(id => {
        const el = document.getElementById(id);
        el.onchange = () => {
            const filtered = applyBrowseFilters(window.__browseData);
            renderFilteredBrowse(filtered);
        };
    });
}

function applyBrowseFilters(data) {
    const docValue = document.getElementById('filterDocument')?.value || '';
    const topicValue = document.getElementById('filterTopic')?.value || '';
    const typeValue = document.getElementById('filterType')?.value || '';
    const diffValue = document.getElementById('filterDifficulty')?.value || '';

    const filtered = { documents: [] };
    data.documents.forEach(d => {
        const name = d.title || d.name;
        if (docValue && name !== docValue) return;
        const newDoc = { title: d.title, name: d.name, document_id: d.document_id, topics: [] };
        d.topics.forEach(t => {
            if (topicValue && t.name !== topicValue) return;
            const newTopic = { name: t.name, cards: [] };
            t.cards.forEach(c => {
                if (typeValue && c.type !== typeValue) return;
                if (diffValue && (c.difficulty || '').toLowerCase() !== diffValue) return;
                newTopic.cards.push(c);
            });
            if (newTopic.cards.length) newDoc.topics.push(newTopic);
        });
        if (newDoc.topics.length) filtered.documents.push(newDoc);
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
                <div class="document-info">${doc.document_id ? `Document ID: ${doc.document_id} | ` : ''}Total Cards: ${doc.topics.reduce((acc,t)=>acc+(t.cards?.length||0),0)}</div>
        `;
        for (const topic of doc.topics) {
            html += `
                <div class="topic-section">
                    <div class="topic-header">📚 ${escapeHtml(topic.name)}</div>
            `;
            for (const card of topic.cards) {
                const typeClass = `card-type-${card.type}`;
                html += `
                    <div class="card-item">
                        <div>
                            <span class="card-type-badge ${typeClass}">${card.type}</span>
                            <span class="card-difficulty">Difficulty: ${card.difficulty || 'N/A'}</span>
                        </div>
                        <div class="card-front">Q: ${escapeHtml(card.front)}</div>
                        <div class="card-back">A: ${escapeHtml(card.back)}</div>
                    </div>
                `;
            }
            html += `</div>`;
        }
        html += `</div>`;
    }
    browseContent.innerHTML = html || "<p class='info'>No cards match the selected filters.</p>";
}

function clearBrowseFilters() {
    ['filterDocument','filterTopic','filterType','filterDifficulty'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    const filtered = applyBrowseFilters(window.__browseData || {documents: []});
    renderFilteredBrowse(filtered);
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

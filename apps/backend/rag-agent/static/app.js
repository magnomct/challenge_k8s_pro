const API_BASE = window.location.origin;

// State
let currentSessionId = null;
let currentDocument = null;
let historyChart = null;

// DOM Elements
const navLinks = document.querySelectorAll('.nav-links li');
const views = document.querySelectorAll('.view-section');
const statusDot = document.querySelector('.status-dot');
const statusText = document.getElementById('api-status');

// Chat DOM
const fileInput = document.getElementById('file-input');
const dropZone = document.getElementById('drop-zone');
const uploadStatus = document.getElementById('upload-status');
const activeDoc = document.getElementById('active-document');
const docName = document.getElementById('doc-name');
const btnRemoveDoc = document.getElementById('btn-remove-doc');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');
const chatMessages = document.getElementById('chat-messages');

// Dashboard DOM
const statTotal = document.getElementById('stat-total');
const statInScope = document.getElementById('stat-in-scope');
const statOutScope = document.getElementById('stat-out-scope');
const statAccuracy = document.getElementById('stat-accuracy');
const tableBody = document.getElementById('history-table-body');
const btnRefreshHistory = document.getElementById('btn-refresh-history');

// Modal DOM
const modalOverlay = document.getElementById('interaction-modal');
const modalContent = document.getElementById('modal-content');
const btnCloseModal = document.querySelector('.close-modal');

// Init
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    setupNavigation();
    setupChatEvents();
    setupDashboardEvents();
    loadDashboardData();
    
    // Set chart defaults to dark theme
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';
});

// Navigation
function setupNavigation() {
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            
            const targetView = link.getAttribute('data-view');
            views.forEach(v => {
                v.classList.remove('active');
                if(v.id === targetView) v.classList.add('active');
            });

            if(targetView === 'dashboard-view') {
                loadDashboardData();
            }
        });
    });
}

// Health Check
async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/health`);
        const data = await res.json();
        
        if (data.status === 'ok') {
            statusDot.className = 'status-dot online';
            statusText.textContent = `API Online (${data.database})`;
        } else {
            statusDot.className = 'status-dot error';
            statusText.textContent = 'API Erro';
        }
    } catch (e) {
        statusDot.className = 'status-dot error';
        statusText.textContent = 'API Offline';
    }
}

// Chat Events
function setupChatEvents() {
    fileInput.addEventListener('change', handleFileUpload);
    
    btnRemoveDoc.addEventListener('click', () => {
        currentSessionId = null;
        currentDocument = null;
        activeDoc.style.display = 'none';
        dropZone.style.display = 'block';
        chatInput.disabled = true;
        btnSend.disabled = true;
        chatMessages.innerHTML = `
            <div class="message system">
                <div class="message-content">Sessão encerrada. Carregue um novo documento.</div>
            </div>
        `;
    });

    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !btnSend.disabled) {
            sendMessage();
        }
    });

    btnSend.addEventListener('click', sendMessage);
}

async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file || file.type !== 'application/pdf') {
        alert('Por favor, selecione um arquivo PDF válido.');
        return;
    }

    dropZone.style.display = 'none';
    uploadStatus.style.display = 'flex';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) throw new Error('Falha no upload');
        
        const data = await res.json();
        currentSessionId = data.session_id;
        currentDocument = data.filename;

        uploadStatus.style.display = 'none';
        activeDoc.style.display = 'flex';
        docName.textContent = currentDocument;
        
        chatInput.disabled = false;
        btnSend.disabled = false;
        chatInput.focus();

        appendMessage('system', `Documento <strong>${currentDocument}</strong> indexado em ${data.chunks} blocos. Pode perguntar!`);

    } catch (error) {
        alert('Erro ao processar o documento: ' + error.message);
        uploadStatus.style.display = 'none';
        dropZone.style.display = 'block';
    }
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text || !currentSessionId) return;

    appendMessage('user', text);
    chatInput.value = '';
    chatInput.disabled = true;
    btnSend.disabled = true;

    const typingId = appendTypingIndicator();

    try {
        const res = await fetch(`${API_BASE}/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                question: text
            })
        });

        const data = await res.json();
        document.getElementById(typingId).remove();

        let metaHtml = '';
        if (data.in_scope) {
            metaHtml = `
                <div class="message-meta">
                    <span style="color: var(--success)"><i class="fa-solid fa-check-circle"></i> No Escopo</span>
                    <span>Distância: ${data.best_distance ? data.best_distance.toFixed(3) : 'N/A'}</span>
                </div>
            `;
        } else {
            metaHtml = `
                <div class="message-meta">
                    <span style="color: var(--warning)"><i class="fa-solid fa-ban"></i> Fora do Escopo</span>
                </div>
            `;
        }

        appendMessage('system', data.answer.replace(/\n/g, '<br>'), metaHtml);

    } catch (error) {
        document.getElementById(typingId).remove();
        appendMessage('system', 'Ocorreu um erro ao buscar a resposta.');
    } finally {
        chatInput.disabled = false;
        btnSend.disabled = false;
        chatInput.focus();
    }
}

function appendMessage(sender, text, metaHtml = '') {
    const div = document.createElement('div');
    div.className = `message ${sender}`;
    div.innerHTML = `
        <div class="message-content">
            ${text}
            ${metaHtml}
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendTypingIndicator() {
    const id = 'typing-' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.className = 'message system';
    div.innerHTML = `
        <div class="message-content">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}


// Dashboard Logic
function setupDashboardEvents() {
    btnRefreshHistory.addEventListener('click', loadDashboardData);
    btnCloseModal.addEventListener('click', () => {
        modalOverlay.classList.remove('active');
    });
}

async function loadDashboardData() {
    try {
        // Load Stats
        const statsRes = await fetch(`${API_BASE}/stats`);
        if (statsRes.ok) {
            const stats = await statsRes.json();
            updateStatsUI(stats);
            renderChart(stats.daily);
        }

        // Load History
        const historyRes = await fetch(`${API_BASE}/history?limit=15`);
        if (historyRes.ok) {
            const history = await historyRes.json();
            renderHistoryTable(history);
        }
    } catch (e) {
        console.error("Dashboard error:", e);
    }
}

function updateStatsUI(stats) {
    statTotal.textContent = stats.total;
    statInScope.textContent = stats.in_scope;
    statOutScope.textContent = stats.out_of_scope;
    statAccuracy.textContent = stats.accuracy_pct + '%';
}

function renderChart(dailyData) {
    const ctx = document.getElementById('historyChart').getContext('2d');
    
    if (historyChart) {
        historyChart.destroy();
    }

    const labels = dailyData.map(d => d.date.substring(5)); // Just MM-DD
    const inScopeData = dailyData.map(d => d.in_scope);
    const outScopeData = dailyData.map(d => d.out_of_scope);

    historyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'No Escopo',
                    data: inScopeData,
                    backgroundColor: '#10b981',
                    borderRadius: 4
                },
                {
                    label: 'Fora do Escopo',
                    data: outScopeData,
                    backgroundColor: '#f59e0b',
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { stacked: true, grid: { display: false } },
                y: { stacked: true, beginAtZero: true }
            },
            plugins: {
                legend: { position: 'top' }
            }
        }
    });
}

function renderHistoryTable(items) {
    tableBody.innerHTML = '';
    
    if(items.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" style="text-align: center;">Nenhum histórico encontrado</td></tr>';
        return;
    }

    items.forEach(item => {
        const tr = document.createElement('tr');
        const dateStr = new Date(item.created_at).toLocaleString('pt-BR');
        
        const statusClass = item.in_scope ? 'success' : 'warning';
        const statusText = item.in_scope ? 'Escopo' : 'Fora';
        
        tr.innerHTML = `
            <td>${dateStr}</td>
            <td>${item.document || 'N/A'}</td>
            <td style="max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${item.question}</td>
            <td><span class="badge-status ${statusClass}">${statusText}</span></td>
            <td>${item.best_distance !== null ? item.best_distance.toFixed(3) : '-'}</td>
        `;
        
        tr.addEventListener('click', () => showInteractionDetails(item));
        tableBody.appendChild(tr);
    });
}

function showInteractionDetails(item) {
    const statusClass = item.in_scope ? 'success' : 'warning';
    const statusText = item.in_scope ? 'Dentro do Escopo' : 'Fora do Escopo';
    
    modalContent.innerHTML = `
        <div class="modal-detail-group">
            <label>Data & Arquivo</label>
            <div class="detail-box">
                <strong>${new Date(item.created_at).toLocaleString('pt-BR')}</strong> &bull; ${item.document || 'Desconhecido'}
            </div>
        </div>
        
        <div class="modal-detail-group">
            <label>Métricas</label>
            <div class="detail-box">
                <span style="color: var(--${statusClass})"><i class="fa-solid fa-circle"></i> ${statusText}</span>
                ${item.best_distance ? `&bull; Distância FAISS: ${item.best_distance.toFixed(4)}` : ''}
            </div>
        </div>
        
        <div class="modal-detail-group">
            <label>Pergunta</label>
            <div class="detail-box" style="background: rgba(59, 130, 246, 0.1); border-color: rgba(59, 130, 246, 0.3);">
                ${item.question}
            </div>
        </div>
        
        <div class="modal-detail-group">
            <label>Resposta</label>
            <div class="detail-box" style="white-space: pre-wrap;">${item.answer}</div>
        </div>
        
        ${item.sources ? `
        <div class="modal-detail-group">
            <label>Fontes Utilizadas</label>
            <div class="detail-box" style="font-size: 0.8rem; color: var(--text-muted);">
                ${item.sources}
            </div>
        </div>
        ` : ''}
    `;
    
    modalOverlay.classList.add('active');
}

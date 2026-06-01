// API Base URL - Change this to your Django server URL
const API_BASE_URL = 'http://127.0.0.1:8000/api/core';

// ========== UI HELPERS ==========
function showRole(role) {
    // Hide all panels
    document.querySelectorAll('.panel').forEach(panel => {
        panel.classList.remove('active');
    });
    
    // Remove active class from all buttons
    document.querySelectorAll('.role-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected panel
    document.getElementById(`${role}-panel`).classList.add('active');
    
    // Add active class to clicked button
    event.target.classList.add('active');
}

function showMessage(elementId, message, isError = false) {
    const element = document.getElementById(elementId);
    element.style.display = 'block';
    element.innerHTML = message;
    element.className = isError ? 'result-card error-card' : 'result-card';
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        element.style.display = 'none';
    }, 5000);
}

// ========== PATIENT PORTAL ==========
async function loadSlots() {
    try {
        const response = await fetch(`${API_BASE_URL}/slots/`);
        const data = await response.json();
        
        if (data.success && data.slots.length > 0) {
            displaySlots(data.slots);
        } else {
            document.getElementById('slots-list').innerHTML = '<p>No available slots found for today or tomorrow.</p>';
        }
    } catch (error) {
        console.error('Error loading slots:', error);
        document.getElementById('slots-list').innerHTML = '<p class="error-card">Error connecting to server. Make sure Django is running.</p>';
    }
}

function displaySlots(slots) {
    const container = document.getElementById('slots-list');
    container.innerHTML = '';
    
    slots.forEach(slot => {
        const slotCard = document.createElement('div');
        slotCard.className = 'slot-card';
        slotCard.onclick = () => selectSlot(slot.slot_id);
        
        slotCard.innerHTML = `
            <h4>👨‍⚕️ ${slot.doctor_name}</h4>
            <p>📅 ${slot.date}</p>
            <p>⏰ ${slot.slot_type.toUpperCase()} (${slot.start_time} - ${slot.end_time})</p>
            <p>🎫 Tokens Available: <strong>${slot.tokens_available}</strong> / ${slot.max_tokens}</p>
            <span class="tokens-left">${slot.tokens_available} spots left</span>
        `;
        
        container.appendChild(slotCard);
    });
}

let selectedSlotId = null;

function selectSlot(slotId) {
    selectedSlotId = slotId;
    document.getElementById('selected-slot-id').value = slotId;
    document.getElementById('booking-form').style.display = 'block';
    
    // Highlight selected slot
    document.querySelectorAll('.slot-card').forEach(card => {
        card.classList.remove('selected');
    });
    event.target.closest('.slot-card').classList.add('selected');
}

function cancelBooking() {
    document.getElementById('booking-form').style.display = 'none';
    document.getElementById('book-token-form').reset();
    selectedSlotId = null;
}

// Book token form submission
document.getElementById('book-token-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const slotId = document.getElementById('selected-slot-id').value;
    const patientName = document.getElementById('patient-name').value;
    const patientAge = document.getElementById('patient-age').value;
    const patientPhone = document.getElementById('patient-phone').value;
    
    if (!slotId) {
        showMessage('booking-result', 'Please select a slot first', true);
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/book/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                slot_id: parseInt(slotId),
                patient_name: patientName,
                patient_age: parseInt(patientAge),
                patient_phone: patientPhone
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const elderlyMsg = data.token.is_elderly ? '🔴 Senior Citizen Priority Applied' : '';
            showMessage('booking-result', `
                ✅ <strong>Booking Successful!</strong><br>
                🎫 Token Number: <strong>${data.token.token_number}</strong><br>
                ⏰ Estimated Time: ${data.token.estimated_time}<br>
                ${elderlyMsg}<br>
                📍 Please arrive 15 minutes before your estimated time.
            `);
            cancelBooking();
            loadSlots(); // Refresh slots
        } else {
            showMessage('booking-result', `❌ Booking Failed: ${data.error}`, true);
        }
    } catch (error) {
        console.error('Error booking token:', error);
        showMessage('booking-result', '❌ Error connecting to server. Make sure Django is running.', true);
    }
});

// ========== RECEPTION PORTAL ==========
async function searchPatient() {
    const searchTerm = document.getElementById('search-input').value;
    
    if (!searchTerm) {
        alert('Please enter a token number or phone number');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/search/?q=${encodeURIComponent(searchTerm)}`);
        const data = await response.json();
        
        const resultsDiv = document.getElementById('search-results');
        
        if (data.success && data.patients.length > 0) {
            resultsDiv.innerHTML = '<h4>Search Results:</h4>';
            data.patients.forEach(patient => {
                resultsDiv.innerHTML += `
                    <div class="queue-item">
                        <div>
                            <strong>🎫 ${patient.token_number}</strong><br>
                            👤 ${patient.patient_name} (${patient.patient_age} yrs)<br>
                            📞 ${patient.patient_phone}<br>
                            Status: ${patient.status}
                        </div>
                        ${patient.status === 'booked' ? 
                            `<button onclick="checkInPatient(${patient.token_id})" class="btn-success">✅ Check In</button>` : 
                            `<span class="priority-badge">${patient.status.toUpperCase()}</span>`
                        }
                    </div>
                `;
            });
        } else {
            resultsDiv.innerHTML = '<p>No patients found with that search term.</p>';
        }
    } catch (error) {
        console.error('Error searching patient:', error);
        document.getElementById('search-results').innerHTML = '<p class="error-card">Error searching. Make sure Django is running.</p>';
    }
}

async function checkInPatient(tokenId) {
    try {
        const response = await fetch(`${API_BASE_URL}/check-in/${tokenId}/`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ ${data.message}`);
            searchPatient(); // Refresh search
            loadWaitingQueue(); // Refresh queue
        } else {
            alert(`❌ Check-in failed: ${data.error}`);
        }
    } catch (error) {
        console.error('Error checking in patient:', error);
        alert('Error checking in patient');
    }
}

async function loadWaitingQueue() {
    try {
        const response = await fetch(`${API_BASE_URL}/waiting-queue/`);
        const data = await response.json();
        
        const queueDiv = document.getElementById('waiting-queue');
        
        if (data.success && data.queue_length > 0) {
            queueDiv.innerHTML = `<h4>🟢 ${data.queue_length} Patients Waiting:</h4>`;
            data.queue.forEach(patient => {
                queueDiv.innerHTML += `
                    <div class="queue-item ${patient.is_elderly ? 'elderly' : ''}">
                        <div>
                            <strong>🎫 ${patient.token_number}</strong><br>
                            👤 ${patient.patient_name} (${patient.patient_age} yrs)<br>
                            ${patient.is_elderly ? '<span class="priority-badge">🔴 PRIORITY (Elderly)</span>' : ''}
                        </div>
                        <div>⏰ Checked in: ${patient.checked_in_at}</div>
                    </div>
                `;
            });
        } else {
            queueDiv.innerHTML = '<p>No patients currently waiting.</p>';
        }
    } catch (error) {
        console.error('Error loading queue:', error);
        document.getElementById('waiting-queue').innerHTML = '<p class="error-card">Error loading queue</p>';
    }
}

// ========== DOCTOR PORTAL ==========
async function loadDoctorQueue() {
    const doctorId = document.getElementById('doctor-select').value;
    
    try {
        const response = await fetch(`${API_BASE_URL}/doctor-queue/${doctorId}/`);
        const data = await response.json();
        
        const queueDiv = document.getElementById('doctor-queue');
        
        if (data.success && data.queue_length > 0) {
            queueDiv.innerHTML = `<h4>👥 ${data.queue_length} Patients in Queue:</h4>`;
            data.queue.forEach(patient => {
                queueDiv.innerHTML += `
                    <div class="queue-item ${patient.is_elderly ? 'elderly' : ''}">
                        <div>
                            <strong>Position ${patient.position} | 🎫 ${patient.token_number}</strong><br>
                            👤 ${patient.patient_name} (${patient.patient_age} yrs)<br>
                            ${patient.is_elderly ? '<span class="priority-badge">🔴 PRIORITY (Elderly)</span>' : ''}
                        </div>
                        <button onclick="setConsultToken(${patient.token_id})" class="btn-primary">Select for Consult</button>
                    </div>
                `;
            });
            
            if (data.next_patient) {
                queueDiv.innerHTML += `
                    <div class="result-card" style="margin-top: 15px;">
                        ⏩ <strong>Next Patient:</strong> ${data.next_patient.patient_name} 
                        (Token: ${data.next_patient.token_number})
                    </div>
                `;
            }
        } else {
            queueDiv.innerHTML = '<p>No patients in your queue.</p>';
        }
    } catch (error) {
        console.error('Error loading doctor queue:', error);
        document.getElementById('doctor-queue').innerHTML = '<p class="error-card">Error loading queue</p>';
    }
}

function setConsultToken(tokenId) {
    document.getElementById('consult-token-id').value = tokenId;
}

async function startConsultation() {
    const tokenId = document.getElementById('consult-token-id').value;
    
    if (!tokenId) {
        alert('Please select a patient from queue or enter Token ID');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/start-consult/${tokenId}/`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('consult-result').innerHTML = `
                <div class="result-card">✅ ${data.message}</div>
            `;
            loadDoctorQueue(); // Refresh queue
            document.getElementById('consult-token-id').value = '';
        } else {
            document.getElementById('consult-result').innerHTML = `
                <div class="result-card error-card">❌ ${data.error}</div>
            `;
        }
    } catch (error) {
        console.error('Error starting consultation:', error);
        document.getElementById('consult-result').innerHTML = '<div class="result-card error-card">❌ Error connecting to server</div>';
    }
}

async function completeConsultation() {
    const tokenId = document.getElementById('consult-token-id').value;
    
    if (!tokenId) {
        alert('Please enter Token ID');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/complete-consult/${tokenId}/`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('consult-result').innerHTML = `
                <div class="result-card">✅ ${data.message}<br>⏱️ Consultation took: ${data.token.consultation_duration_minutes} minutes</div>
            `;
            loadDoctorQueue(); // Refresh queue
            document.getElementById('consult-token-id').value = '';
        } else {
            document.getElementById('consult-result').innerHTML = `
                <div class="result-card error-card">❌ ${data.error}</div>
            `;
        }
    } catch (error) {
        console.error('Error completing consultation:', error);
        document.getElementById('consult-result').innerHTML = '<div class="result-card error-card">❌ Error connecting to server</div>';
    }
}

// Load initial data when panels are shown
setInterval(() => {
    // Auto-refresh queue every 10 seconds if reception or doctor panel is active
    if (document.getElementById('reception-panel').classList.contains('active')) {
        loadWaitingQueue();
    }
    if (document.getElementById('doctor-panel').classList.contains('active')) {
        loadDoctorQueue();
    }
}, 10000);
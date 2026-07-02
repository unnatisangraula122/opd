// Smart OPD System - Core Utilities

// Toast Notification
class Toast {
    static container = null;
    static init() { if (!this.container) { this.container = document.createElement('div'); this.container.className = 'toast-container'; document.body.appendChild(this.container); } }
    static show(message, type = 'info') {
        this.init();
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        const icons = { success: '✓', error: '✗', warning: '⚠', info: 'ℹ' };
        toast.innerHTML = `<span style="font-size:1.25rem;">${icons[type] || 'ℹ'}</span><span>${message}</span>`;
        this.container.appendChild(toast);
        setTimeout(() => { toast.style.animation = 'slideOut 0.3s ease'; setTimeout(() => toast.remove(), 300); }, 3000);
    }
}

// Loading Overlay
class LoadingOverlay {
    static show() { const overlay = document.createElement('div'); overlay.id = 'loading-overlay'; overlay.className = 'loading-overlay'; overlay.innerHTML = '<div class="spinner"></div>'; document.body.appendChild(overlay); }
    static hide() { document.getElementById('loading-overlay')?.remove(); }
}

// Storage Manager
const StorageManager = {
    set(key, value) { localStorage.setItem(`smartOPD_${key}`, JSON.stringify(value)); },
    get(key) { const data = localStorage.getItem(`smartOPD_${key}`); return data ? JSON.parse(data) : null; },
    remove(key) { localStorage.removeItem(`smartOPD_${key}`); },
    getUser() { return this.get('user'); },
    setUser(user) { this.set('user', user); },
    logout() { this.remove('user'); window.location.href = '/index.html'; },
    getBookings() { return this.get('bookings') || []; },
    addBooking(booking) { const bookings = this.getBookings(); bookings.push(booking); this.set('bookings', bookings); },
    getLabReports() { return this.get('labReports') || []; },
    addLabReport(report) { const reports = this.getLabReports(); reports.push(report); this.set('labReports', reports); },
    getBills() { return this.get('bills') || []; },
    addBill(bill) { const bills = this.getBills(); bills.push(bill); this.set('bills', bills); }
};

// Time Utilities
const TimeUtils = {
    getCurrentTime() { return new Date(); },
    formatTime(date) { return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }); },
    formatDate(date) { return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }); },
    isSlotPassed(slotType) {
        const now = new Date();
        const hour = now.getHours();
        const minute = now.getMinutes();
        const slotEnds = { 'MORNING': 11, 'AFTERNOON': 14, 'EVENING': 17 };
        const endHour = slotEnds[slotType];
        if (!endHour) return false;
        return (hour > endHour) || (hour === endHour && minute >= 0);
    },
    isWithinCheckInWindow(slotType, checkInTime) {
        const slotStart = { 'MORNING': 9, 'AFTERNOON': 12, 'EVENING': 15 };
        const startHour = slotStart[slotType];
        const checkInHour = checkInTime.getHours();
        const checkInMinute = checkInTime.getMinutes();
        return checkInHour >= startHour && checkInHour < (startHour + 2);
    }
};

// Export
window.Toast = Toast;
window.LoadingOverlay = LoadingOverlay;
window.StorageManager = StorageManager;
window.TimeUtils = TimeUtils;
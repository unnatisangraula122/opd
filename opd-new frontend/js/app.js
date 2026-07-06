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
    logout() { this.remove('user'); window.location.href = '../index.html'; },
    getBookings() { return this.get('bookings') || []; },
    addBooking(booking) { const bookings = this.getBookings(); bookings.push(booking); this.set('bookings', bookings); },
    getLabReports() { return this.get('labReports') || []; },
    addLabReport(report) { const reports = this.getLabReports(); reports.push(report); this.set('labReports', reports); },
    getBills() { return this.get('bills') || []; },
    addBill(bill) { const bills = this.getBills(); bills.push(bill); this.set('bills', bills); }
};

// Time Utilities — shared slot status logic (matches backend ConsultationSlot times)
const TimeUtils = {
    SLOT_CONFIG: {
        MORNING: {
            startHour: 9, startMinute: 0, endHour: 11, endMinute: 0,
            startTime: '09:00', endTime: '11:00',
            displayTime: '9:00 AM - 11:00 AM',
            checkinOpensMinutesBefore: 15,
        },
        AFTERNOON: {
            startHour: 12, startMinute: 0, endHour: 14, endMinute: 0,
            startTime: '12:00', endTime: '14:00',
            displayTime: '12:00 PM - 2:00 PM',
            checkinOpensMinutesBefore: 15,
        },
        EVENING: {
            startHour: 15, startMinute: 0, endHour: 17, endMinute: 0,
            startTime: '15:00', endTime: '17:00',
            displayTime: '3:00 PM - 5:00 PM',
            checkinOpensMinutesBefore: 15,
        },
    },

    getCurrentTime() { return new Date(); },

    formatTime(date) {
        return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    },

    formatDate(date) {
        return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    },

    normalizeSlotType(slotType) {
        if (!slotType) return null;
        const raw = String(slotType).trim().toUpperCase();
        if (raw.startsWith('MORNING') || raw === 'M') return 'MORNING';
        if (raw.startsWith('AFTERNOON') || raw === 'A') return 'AFTERNOON';
        if (raw.startsWith('EVENING') || raw === 'E') return 'EVENING';
        return raw;
    },

    parseDate(dateInput) {
        if (!dateInput) return null;
        if (dateInput instanceof Date) return new Date(dateInput.getTime());
        const parsed = new Date(`${String(dateInput).slice(0, 10)}T00:00:00`);
        return Number.isNaN(parsed.getTime()) ? null : parsed;
    },

    isSameLocalDay(a, b) {
        const left = this.parseDate(a);
        const right = this.parseDate(b);
        if (!left || !right) return false;
        return left.getFullYear() === right.getFullYear()
            && left.getMonth() === right.getMonth()
            && left.getDate() === right.getDate();
    },

    parseClockToMinutes(timeStr) {
        if (!timeStr) return null;
        const value = String(timeStr).trim();
        const match24 = value.match(/^(\d{1,2}):(\d{2})$/);
        if (match24) return parseInt(match24[1], 10) * 60 + parseInt(match24[2], 10);
        const match12 = value.match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
        if (match12) {
            let hour = parseInt(match12[1], 10);
            const minute = parseInt(match12[2], 10);
            const meridiem = match12[3].toUpperCase();
            if (meridiem === 'PM' && hour !== 12) hour += 12;
            if (meridiem === 'AM' && hour === 12) hour = 0;
            return hour * 60 + minute;
        }
        return null;
    },

    getSlotBounds(appointment) {
        const slotType = this.normalizeSlotType(
            appointment.slot || appointment.slot_type || appointment.slot_type_raw
        );
        const config = slotType ? this.SLOT_CONFIG[slotType] : null;
        const startMinutes = this.parseClockToMinutes(appointment.start_time)
            ?? (config ? config.startHour * 60 + config.startMinute : null);
        const endMinutes = this.parseClockToMinutes(appointment.end_time)
            ?? (config ? config.endHour * 60 + config.endMinute : null);
        const checkinOpensBefore = config?.checkinOpensMinutesBefore ?? 15;
        const checkinOpenMinutes = startMinutes != null
            ? Math.max(0, startMinutes - checkinOpensBefore)
            : null;
        return {
            slotType,
            startMinutes,
            endMinutes,
            checkinOpenMinutes,
            displayTime: config?.displayTime || '',
        };
    },

    nowMinutes(now = new Date()) {
        return now.getHours() * 60 + now.getMinutes();
    },

    compareAppointmentDay(appointmentDate, now = new Date()) {
        const aptDate = this.parseDate(appointmentDate);
        if (!aptDate) return 'unknown';
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const day = new Date(aptDate.getFullYear(), aptDate.getMonth(), aptDate.getDate());
        if (day.getTime() > today.getTime()) return 'future';
        if (day.getTime() < today.getTime()) return 'past';
        return 'today';
    },

    getCurrentSlot(now = new Date()) {
        const current = this.nowMinutes(now);
        for (const [slotType, config] of Object.entries(this.SLOT_CONFIG)) {
            const start = config.startHour * 60 + config.startMinute;
            const end = config.endHour * 60 + config.endMinute;
            if (current >= start && current < end) return slotType;
        }
        return null;
    },

    getAppointmentSlotStatus(appointment, now = new Date()) {
        const tokenStatus = String(appointment.status || '').toLowerCase().replace('_', '-');
        const bounds = this.getSlotBounds(appointment);
        const dayRelation = this.compareAppointmentDay(appointment.date, now);
        const currentMinutes = this.nowMinutes(now);

        if (tokenStatus === 'completed') {
            return {
                status: 'completed', label: 'Completed', class: 'status-completed', icon: '✓',
                isPassed: false, isActive: false, isUpcoming: false, canCheckIn: false,
            };
        }
        if (tokenStatus === 'checked-in' || tokenStatus === 'checked_in') {
            return {
                status: 'in_queue', label: 'In Queue', class: 'status-ongoing', icon: '⏳',
                isPassed: false, isActive: true, isUpcoming: false, canCheckIn: false,
            };
        }
        if (tokenStatus === 'cancelled') {
            return {
                status: 'cancelled', label: 'Cancelled', class: 'status-expired', icon: '✗',
                isPassed: true, isActive: false, isUpcoming: false, canCheckIn: false,
            };
        }
        if (tokenStatus === 'expired') {
            return {
                status: 'passed', label: 'Passed', class: 'status-expired', icon: '⛔',
                isPassed: true, isActive: false, isUpcoming: false, canCheckIn: false,
            };
        }

        if (dayRelation === 'future') {
            return {
                status: 'upcoming', label: 'Upcoming', class: 'status-upcoming', icon: '📅',
                isPassed: false, isActive: false, isUpcoming: true, canCheckIn: false,
            };
        }
        if (dayRelation === 'past') {
            return {
                status: 'passed', label: 'Passed', class: 'status-expired', icon: '⛔',
                isPassed: true, isActive: false, isUpcoming: false, canCheckIn: false,
            };
        }

        if (bounds.startMinutes == null || bounds.endMinutes == null) {
            return {
                status: 'unknown', label: 'Unknown', class: '', icon: '?',
                isPassed: false, isActive: false, isUpcoming: false, canCheckIn: false,
            };
        }

        if (currentMinutes < bounds.startMinutes) {
            const canCheckIn = currentMinutes >= bounds.checkinOpenMinutes
                && (tokenStatus === 'booked' || tokenStatus === 'pending');
            return {
                status: 'upcoming', label: 'Upcoming', class: 'status-upcoming', icon: '📅',
                isPassed: false, isActive: false, isUpcoming: true, canCheckIn,
            };
        }
        if (currentMinutes >= bounds.startMinutes && currentMinutes <= bounds.endMinutes) {
            const canCheckIn = tokenStatus === 'booked' || tokenStatus === 'pending';
            return {
                status: 'active', label: 'Active', class: 'status-ongoing', icon: '🔄',
                isPassed: false, isActive: true, isUpcoming: false, canCheckIn,
            };
        }
        return {
            status: 'passed', label: 'Passed', class: 'status-expired', icon: '⛔',
            isPassed: true, isActive: false, isUpcoming: false, canCheckIn: false,
        };
    },

    isSlotPassed(slotType, date = null, now = new Date()) {
        const appointmentDate = date || now;
        return this.getAppointmentSlotStatus(
            { slot: slotType, date: appointmentDate, status: 'booked' },
            now
        ).isPassed;
    },

    isSlotActive(slotType, date = null, now = new Date()) {
        const appointmentDate = date || now;
        return this.getAppointmentSlotStatus(
            { slot: slotType, date: appointmentDate, status: 'booked' },
            now
        ).isActive;
    },

    isSlotUpcoming(slotType, date = null, now = new Date()) {
        const appointmentDate = date || now;
        return this.getAppointmentSlotStatus(
            { slot: slotType, date: appointmentDate, status: 'booked' },
            now
        ).isUpcoming;
    },

    canCheckIn(appointment, now = new Date()) {
        return this.getAppointmentSlotStatus(appointment, now).canCheckIn;
    },

    isWithinCheckInWindow(slotType, checkInTime, date = null) {
        const appointmentDate = date || checkInTime;
        const bounds = this.getSlotBounds({ slot: slotType, date: appointmentDate });
        if (bounds.checkinOpenMinutes == null || bounds.endMinutes == null) return false;
        const arrival = this.nowMinutes(checkInTime);
        return arrival >= bounds.checkinOpenMinutes && arrival <= bounds.endMinutes;
    },
};

// Export
window.Toast = Toast;
window.LoadingOverlay = LoadingOverlay;
window.StorageManager = StorageManager;
window.TimeUtils = TimeUtils;
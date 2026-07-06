// Smart OPD — Django API client (session + CSRF)

const API = {
    base: '/api/core',

    getCookie(name) {
        const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return match ? decodeURIComponent(match[2]) : null;
    },

    async ensureCsrf() {
        if (this.getCookie('csrftoken')) return;
        await fetch(`${this.base}/csrf/`, { credentials: 'include' });
    },

    async request(method, path, body = null, isForm = false) {
        await this.ensureCsrf();
        const headers = { 'X-CSRFToken': this.getCookie('csrftoken') || '' };
        const opts = { method, credentials: 'include', headers };
        if (body !== null) {
            if (isForm) {
                opts.body = body;
            } else {
                headers['Content-Type'] = 'application/json';
                opts.body = JSON.stringify(body);
            }
        }
        const res = await fetch(`${this.base}${path}`, opts);
        let data;
        try {
            data = await res.json();
        } catch {
            data = { success: false, error: 'Invalid server response' };
        }
        if (!res.ok && !data.error) data.error = `Request failed (${res.status})`;
        return data;
    },

    get(path) { return this.request('GET', path); },
    post(path, body) { return this.request('POST', path, body); },
    put(path, body) { return this.request('PUT', path, body); },

    // Auth
    patientRegister(d) { return this.post('/patient/register/', d); },
    patientLogin(d) { return this.post('/patient/login/', d); },
    patientLoginOtp(d) { return this.post('/patient/login/otp/', d); },
    patientLogout() { return this.post('/patient/logout/', {}); },
    patientMe() { return this.get('/patient/me/'); },
    patientResetPassword(d) { return this.post('/patient/reset-password/', d); },
    otpSend(d) { return this.post('/otp/send/', d); },
    otpVerify(d) { return this.post('/otp/verify/', d); },
    validateOldPatient(d) { return this.post('/patient/validate/', d); },
    lookupPatient(patientId, phone) {
        let q = `patient_id=${encodeURIComponent(patientId)}`;
        if (phone) q += `&phone=${encodeURIComponent(phone)}`;
        return this.get(`/patient/lookup/?${q}`);
    },
    staffLogin(d) { return this.post('/auth/staff/login/', d); },
    staffLogout() { return this.post('/auth/staff/logout/', {}); },
    authMe() { return this.get('/auth/me/'); },

    // Booking
    getSlots(date) { return this.get(`/slots/${date ? '?date=' + date : ''}`); },
    bookToken(d) { return this.post('/book/', d); },
    cancelToken(id) { return this.post(`/cancel/${id}/`, {}); },

    // Patient portal
    patientTokens() { return this.get('/patient/tokens/'); },
    patientQueueStatus() { return this.get('/patient/queue-status/'); },
    patientPrescriptions() { return this.get('/patient/prescriptions/'); },
    patientLabReports() { return this.get('/patient/lab-reports/'); },
    patientBills() { return this.get('/patient/bills/'); },

    // Reception
    searchPatient(q) { return this.get(`/search/?q=${encodeURIComponent(q)}`); },
    checkIn(tokenId, d) { return this.post(`/check-in/${tokenId}/`, d || {}); },
    receptionRegister(d) { return this.post('/reception/register/', d); },
    receptionAppointments() { return this.get('/reception/appointments/'); },
    receptionLabPayments() { return this.get('/reception/lab-payments/'); },
    payLabFee(orderId, d) { return this.post(`/reception/lab-pay/${orderId}/`, d || {}); },
    throttleStatus() { return this.get('/reception/throttle/'); },
    waitingQueue(doctorId) {
        return this.get(doctorId ? `/waiting-queue/${doctorId}/` : '/waiting-queue/');
    },

    // Doctor
    doctorSchedule() { return this.get('/doctor/schedule/'); },
    doctorQueue() { return this.get('/doctor-queue/'); },
    nextPatient() { return this.get('/next-patient/'); },
    startConsult(tokenId) { return this.post(`/start-consult/${tokenId}/`, {}); },
    completeConsult(tokenId, d) { return this.post(`/complete-consult/${tokenId}/`, d); },

    // Lab
    labQueue() { return this.get('/lab/queue/'); },
    labStart(orderId) { return this.post(`/lab/orders/${orderId}/start/`, {}); },
    labComplete(orderId, formData) { return this.request('POST', `/lab/orders/${orderId}/complete/`, formData, true); },

    // Pharmacy
    pharmacyQueue() { return this.get('/pharmacy/queue/'); },
    pharmacyStart(entryId) { return this.post(`/pharmacy/${entryId}/start/`, {}); },
    pharmacyComplete(entryId, d) { return this.post(`/pharmacy/${entryId}/complete/`, d || {}); },

    // Admin
    analytics() { return this.get('/analytics/'); },
    adminDoctors() { return this.get('/admin/doctors/'); },
    adminAddDoctor(d) { return this.post('/admin/doctors/add/', d); },
    adminUpdateDoctor(id, d) { return this.put(`/admin/doctors/${id}/`, d); },
    adminSlotConfig() { return this.get('/admin/slots/config/'); },
    adminSaveSlotConfig(d) { return this.put('/admin/slots/config/', d); },
    adminThrottleConfig() { return this.get('/admin/throttle/config/'); },
    adminSaveThrottleConfig(d) { return this.put('/admin/throttle/config/', d); },
    adminThrottleLogs() { return this.get('/admin/throttle/logs/'); },

    requireStaff(roles, redirectUrl = '../staff/login.html') {
        return this.authMe().then(data => {
            if (!data.success || !data.user || !roles.includes(data.user.role)) {
                window.location.href = redirectUrl;
                return null;
            }
            return data.user;
        });
    },

    requirePatient(redirectUrl = 'login.html') {
        return this.authMe().then(data => {
            if (!data.success || !data.user || data.user.role !== 'patient') {
                window.location.href = redirectUrl;
                return null;
            }
            return data.user;
        });
    },
};

window.API = API;

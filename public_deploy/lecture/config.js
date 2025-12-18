// Configuration for the PDF Lecture Player

const CONFIG = {
    // Backend API Endpoints (Cloud Run URLs)
    // You can find these by running: ./deploy.sh
    API_ENDPOINTS: {
        UPLOAD: 'https://upload-pdf-xyaszg3aua-uw.a.run.app',
        STATUS: 'https://get-job-status-xyaszg3aua-uw.a.run.app',
        AGENTS: 'https://manage-agents-xyaszg3aua-uw.a.run.app'
    },

    // Polling interval in milliseconds
    POLL_INTERVAL: 3000
};

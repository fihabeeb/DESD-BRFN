function qualityScan() {
    return {
        mode: 'upload',
        dragOver: false,
        imagePreview: null,
        imageFile: null,
        scanning: false,
        results: null,
        scanError: null,
        cameraActive: false,
        cameraError: null,
        stream: null,

        switchMode(newMode) {
            if (this.mode === 'camera' && newMode !== 'camera') {
                this.stopCamera();
            }
            this.mode = newMode;
        },

        handleFileSelect(event) {
            const file = event.target.files[0];
            if (file) this.loadImage(file);
        },

        handleDrop(event) {
            this.dragOver = false;
            const file = event.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) this.loadImage(file);
        },

        loadImage(file) {
            this.imageFile = file;
            this.results = null;
            this.scanError = null;
            const reader = new FileReader();
            reader.onload = (e) => { this.imagePreview = e.target.result; };
            reader.readAsDataURL(file);
        },

        async startCamera() {
            this.cameraError = null;
            try {
                this.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
                this.$refs.video.srcObject = this.stream;
                this.cameraActive = true;
            } catch (err) {
                this.cameraError = 'Could not access camera: ' + (err.message || err.name);
            }
        },

        stopCamera() {
            if (this.stream) {
                this.stream.getTracks().forEach(t => t.stop());
                this.stream = null;
            }
            this.cameraActive = false;
        },

        capturePhoto() {
            const video = this.$refs.video;
            const canvas = this.$refs.canvas;
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            this.imagePreview = canvas.toDataURL('image/jpeg');
            canvas.toBlob(blob => {
                this.imageFile = new File([blob], 'capture.jpg', { type: 'image/jpeg' });
            }, 'image/jpeg', 0.92);
            this.stopCamera();
            this.results = null;
            this.scanError = null;
        },

        clearImage() {
            this.imagePreview = null;
            this.imageFile = null;
            this.results = null;
            this.scanError = null;
            if (this.$refs.fileInput) this.$refs.fileInput.value = '';
        },

        clearResults() {
            this.clearImage();
        },

        async submitScan() {
            if (!this.imageFile) return;
            this.scanning = true;
            this.results = null;
            this.scanError = null;

            const formData = new FormData();
            formData.append('image', this.imageFile);

            try {
                const response = await fetch(QUALITY_SCAN_URL, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCsrfToken() },
                    body: formData,
                });
                const data = await response.json();
                if (!response.ok || !data.success) {
                    this.scanError = data.error || 'Something went wrong. Please try again.';
                } else {
                    this.results = data;
                }
            } catch (err) {
                this.scanError = 'Network error. Please check your connection and try again.';
            } finally {
                this.scanning = false;
            }
        },

        scoreColor(score) {
            if (score === null || score === undefined) return '#9ca3af';
            if (score >= 80) return '#16a34a';
            if (score >= 60) return '#d97706';
            return '#dc2626';
        },

        scoreDash(score) {
            const circumference = 2 * Math.PI * 14;
            if (score === null || score === undefined) return `0 ${circumference}`;
            const filled = (score / 100) * circumference;
            return `${filled} ${circumference}`;
        },
    };
}

function getCsrfToken() {
    const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
    return cookie ? cookie.trim().split('=')[1] : '';
}

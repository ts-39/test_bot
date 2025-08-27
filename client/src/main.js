
class VoiceBotClient {
    constructor() {
        this.ws = null;
        this.audioContext = null;
        this.mediaStream = null;
        this.audioWorkletNode = null;
        this.isConnected = false;
        this.isMuted = false;
        this.isListening = false;
        this.isSpeaking = false;
        
        this.sampleRate = 16000;
        this.frameSize = 320; // 20ms at 16kHz
        this.bufferSize = 4096;
        
        this.wsUrl = this.getWebSocketUrl();
        this.clientId = this.generateClientId();
        
        this.statusEl = document.getElementById('status');
        this.connectBtn = document.getElementById('connectBtn');
        this.muteBtn = document.getElementById('muteBtn');
        this.visualizerEl = document.getElementById('visualizer');
        
        this.initializeUI();
        this.createAudioVisualizer();
    }
    
    getWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;
        const port = import.meta.env.VITE_WS_PORT || '8000';
        return `${protocol}//${host}:${port}/ws`;
    }
    
    generateClientId() {
        return 'client_' + Math.random().toString(36).substr(2, 9);
    }
    
    initializeUI() {
        this.connectBtn.addEventListener('click', () => {
            if (this.isConnected) {
                this.disconnect();
            } else {
                this.connect();
            }
        });
        
        this.muteBtn.addEventListener('click', () => {
            this.toggleMute();
        });
        
        this.updateStatus('disconnected', '接続待機中');
    }
    
    createAudioVisualizer() {
        for (let i = 0; i < 32; i++) {
            const bar = document.createElement('div');
            bar.className = 'visualizer-bar';
            bar.style.height = '2px';
            this.visualizerEl.appendChild(bar);
        }
    }
    
    updateAudioVisualizer(audioData) {
        const bars = this.visualizerEl.querySelectorAll('.visualizer-bar');
        const dataLength = audioData.length;
        const barCount = bars.length;
        const samplesPerBar = Math.floor(dataLength / barCount);
        
        for (let i = 0; i < barCount; i++) {
            let sum = 0;
            const start = i * samplesPerBar;
            const end = start + samplesPerBar;
            
            for (let j = start; j < end && j < dataLength; j++) {
                sum += Math.abs(audioData[j]);
            }
            
            const average = sum / samplesPerBar;
            const height = Math.min(50, (average / 32768) * 50); // Normalize to 0-50px
            bars[i].style.height = `${Math.max(2, height)}px`;
        }
    }
    
    async connect() {
        try {
            this.updateStatus('connecting', '接続中...');
            
            await this.initializeAudio();
            
            await this.connectWebSocket();
            
            this.isConnected = true;
            this.connectBtn.textContent = '切断';
            this.muteBtn.disabled = false;
            this.updateStatus('connected', '接続済み');
            
        } catch (error) {
            console.error('Connection failed:', error);
            this.updateStatus('disconnected', '接続失敗: ' + error.message);
            this.cleanup();
        }
    }
    
    async initializeAudio() {
        try {
            try {
                this.mediaStream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        sampleRate: this.sampleRate,
                        channelCount: 1,
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    }
                });
                console.log('Real microphone initialized');
                await this.setupRealAudio();
            } catch (micError) {
                console.warn('Real microphone not available, using mock audio:', micError.message);
                await this.setupMockAudio();
            }
            
        } catch (error) {
            throw new Error('オーディオ初期化に失敗しました: ' + error.message);
        }
    }
    
    async setupRealAudio() {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: this.sampleRate
        });
        
        await this.audioContext.audioWorklet.addModule('/src/audio-processor.js');
        
        this.audioWorkletNode = new AudioWorkletNode(this.audioContext, 'audio-processor', {
            processorOptions: {
                frameSize: this.frameSize
            }
        });
        
        const source = this.audioContext.createMediaStreamSource(this.mediaStream);
        source.connect(this.audioWorkletNode);
        this.audioWorkletNode.connect(this.audioContext.destination);
        
        this.audioWorkletNode.port.onmessage = (event) => {
            const { type, data } = event.data;
            
            if (type === 'audioData' && !this.isMuted) {
                this.sendAudioData(data);
                this.updateAudioVisualizer(data);
                this.updateStatus('listening', '音声認識中...');
            }
        };
    }
    
    async setupMockAudio() {
        this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: this.sampleRate
        });
        
        console.log('Mock audio mode: simulating audio input for testing');
        
        this.mockAudioInterval = setInterval(() => {
            if (!this.isMuted && this.isConnected) {
                const mockData = new Float32Array(this.frameSize);
                for (let i = 0; i < mockData.length; i++) {
                    mockData[i] = (Math.random() - 0.5) * 0.01; // Very quiet noise
                }
                
                this.sendAudioData(mockData);
                this.updateAudioVisualizer(mockData);
                
                if (Math.random() < 0.1) { // 10% chance
                    this.updateStatus('listening', '音声認識中... (テストモード)');
                }
            }
        }, 20); // 20ms intervals to match frameSize
    }
    
    async connectWebSocket() {
        return new Promise((resolve, reject) => {
            const wsUrl = `${this.wsUrl}/${this.clientId}`;
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.sendControlMessage({ type: 'ready' });
                resolve();
            };
            
            this.ws.onmessage = (event) => {
                if (event.data instanceof ArrayBuffer) {
                    this.playAudioResponse(event.data);
                } else {
                    const message = JSON.parse(event.data);
                    this.handleControlMessage(message);
                }
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                reject(new Error('WebSocket接続エラー'));
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.isConnected = false;
                this.connectBtn.textContent = '接続';
                this.muteBtn.disabled = true;
                this.updateStatus('disconnected', '切断されました');
            };
        });
    }
    
    sendAudioData(audioData) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const pcmData = new Int16Array(audioData.length);
            for (let i = 0; i < audioData.length; i++) {
                pcmData[i] = Math.max(-32768, Math.min(32767, audioData[i] * 32768));
            }
            
            this.ws.send(pcmData.buffer);
        }
    }
    
    sendControlMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        }
    }
    
    handleControlMessage(message) {
        console.log('Control message received:', message);
        
        switch (message.type) {
            case 'ready_ack':
                console.log('Server ready for audio processing');
                break;
                
            case 'pong':
                console.log('Pong received');
                break;
                
            case 'config_updated':
                console.log('Configuration updated');
                break;
                
            case 'error':
                console.error('Server error:', message.message);
                this.updateStatus('disconnected', 'エラー: ' + message.message);
                break;
                
            default:
                console.log('Unknown message type:', message.type);
        }
    }
    
    async playAudioResponse(audioBuffer) {
        try {
            this.updateStatus('speaking', 'ボット応答中...');
            
            const audioData = await this.audioContext.decodeAudioData(audioBuffer.slice());
            
            const source = this.audioContext.createBufferSource();
            source.buffer = audioData;
            source.connect(this.audioContext.destination);
            
            source.onended = () => {
                this.updateStatus('connected', '接続済み');
            };
            
            source.start();
            
        } catch (error) {
            console.error('Error playing audio response:', error);
            this.updateStatus('connected', '接続済み');
        }
    }
    
    toggleMute() {
        this.isMuted = !this.isMuted;
        this.muteBtn.textContent = this.isMuted ? 'ミュート解除' : 'ミュート';
        
        if (this.isMuted) {
            this.updateStatus('connected', 'ミュート中');
        } else {
            this.updateStatus('connected', '接続済み');
        }
    }
    
    disconnect() {
        this.cleanup();
        this.updateStatus('disconnected', '切断しました');
    }
    
    cleanup() {
        if (this.mockAudioInterval) {
            clearInterval(this.mockAudioInterval);
            this.mockAudioInterval = null;
        }
        
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        if (this.audioWorkletNode) {
            this.audioWorkletNode.disconnect();
            this.audioWorkletNode = null;
        }
        
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        
        this.isConnected = false;
        this.connectBtn.textContent = '接続';
        this.muteBtn.disabled = true;
        this.muteBtn.textContent = 'ミュート';
        this.isMuted = false;
    }
    
    updateStatus(type, message) {
        this.statusEl.className = `status ${type}`;
        this.statusEl.textContent = message;
    }
}

function startPingInterval(client) {
    setInterval(() => {
        if (client.isConnected) {
            client.sendControlMessage({ type: 'ping' });
        }
    }, 30000); // 30 seconds
}

document.addEventListener('DOMContentLoaded', () => {
    const client = new VoiceBotClient();
    startPingInterval(client);
    
    window.addEventListener('beforeunload', () => {
        client.cleanup();
    });
});
